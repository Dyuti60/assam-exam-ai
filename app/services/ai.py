import json
import re
import string
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import (
    validate_ai_max_output_tokens,
    validate_ai_model_identifier,
    validate_ai_request_timeout,
    validate_ai_temperature,
)
from app.models import AiExecutionRun, AiPromptVersion
from app.repositories import AiRepository
from app.schemas.ai import (
    AiExecutionRunResponse,
    AiPromptVersionCreate,
    AiPromptVersionResponse,
)

_MAX_PROVIDER_OUTPUT_CHARACTERS = 1_000_000
_MAX_PROVIDER_TOKEN_COUNT = 2_147_483_647
_MAX_PROVIDER_COST = Decimal(1_000_000_000_000)
_PROVIDER_COST_PATTERN = re.compile(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$")
_PROVIDER_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")
_PROVIDER_ERROR_CODES = frozenset(
    {
        "AI_PROVIDER_AUTHENTICATION",
        "AI_PROVIDER_DISABLED",
        "AI_PROVIDER_ERROR",
        "AI_PROVIDER_INVALID_RESPONSE",
        "AI_PROVIDER_RATE_LIMITED",
        "AI_PROVIDER_RESPONSE_INVALID",
        "AI_PROVIDER_SAFETY_BLOCKED",
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_TRANSPORT",
        "AI_PROVIDER_UNAVAILABLE",
    }
)


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def prompt_checksum(data: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(dict(data)))


class AiResourceNotFoundError(Exception):
    def __init__(self, resource: str, resource_id: int) -> None:
        super().__init__(f"{resource} {resource_id} not found")


class AiResourceConflictError(Exception):
    pass


class AiExecutionRejectedError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


class AiProviderError(Exception):
    def __init__(self, error_code: str) -> None:
        self.error_code = error_code
        super().__init__(error_code)


@dataclass(frozen=True)
class AiProviderRequest:
    request_id: str
    model_id: str
    system_prompt: str
    user_prompt: str
    output_schema: dict[str, Any]
    timeout_seconds: float
    max_output_tokens: int
    temperature: float


@dataclass(frozen=True)
class AiProviderResult:
    output_text: str
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider_cost: str | None = None
    cost_currency: str | None = None
    finish_reason: str | None = None
    safety_metadata: dict[str, Any] | None = None


class AiProvider(Protocol):
    key: str

    def generate(self, request: AiProviderRequest) -> AiProviderResult: ...


@dataclass(frozen=True)
class AiExecutionOptions:
    model_id: str
    timeout_seconds: float
    max_output_tokens: int
    temperature: float
    allowed_models: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "model_id",
            validate_ai_model_identifier(self.model_id, allow_blank=True),
        )
        object.__setattr__(
            self, "timeout_seconds", validate_ai_request_timeout(self.timeout_seconds)
        )
        object.__setattr__(
            self,
            "max_output_tokens",
            validate_ai_max_output_tokens(self.max_output_tokens),
        )
        object.__setattr__(
            self, "temperature", validate_ai_temperature(self.temperature)
        )
        if type(self.allowed_models) not in (frozenset, set, tuple, list):
            raise ValueError("AI model allowlist is invalid")
        try:
            validated_models = [
                validate_ai_model_identifier(allowed_model, allow_blank=False)
                for allowed_model in self.allowed_models
            ]
            allowed_models = frozenset(validated_models)
        except Exception:  # noqa: BLE001 -- allowlist containers are untrusted
            raise ValueError("AI model allowlist is invalid") from None
        if self.model_id and allowed_models and self.model_id not in allowed_models:
            raise ValueError("AI model is not allowed")
        object.__setattr__(self, "allowed_models", allowed_models)


@dataclass(frozen=True)
class _PromptSnapshot:
    id: int
    prompt_key: str
    version: int
    system_template: str
    user_template: str
    input_schema_key: str
    input_schema_version: int
    output_schema_key: str
    output_schema_version: int
    checksum: str


class AiPromptService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = AiRepository(session)

    def create(self, request: AiPromptVersionCreate) -> AiPromptVersionResponse:
        data = request.model_dump()
        prompt = AiPromptVersion(**data, checksum=prompt_checksum(data))
        try:
            self.repository.add_prompt_version(prompt)
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            if _constraint_name(error) == "uq_ai_prompt_versions_key_version":
                raise AiResourceConflictError(
                    f"AiPromptVersion {request.prompt_key} version {request.version} already exists"
                ) from error
            raise
        except Exception:
            self.session.rollback()
            raise
        return AiPromptVersionResponse.model_validate(prompt)

    def get(self, prompt_id: int) -> AiPromptVersionResponse:
        prompt = self.repository.get_prompt_version(prompt_id)
        if prompt is None:
            raise AiResourceNotFoundError("AiPromptVersion", prompt_id)
        return AiPromptVersionResponse.model_validate(prompt)


class AiAuditService:
    def __init__(self, session: Session) -> None:
        self.repository = AiRepository(session)

    def get(self, execution_id: int) -> AiExecutionRunResponse:
        execution = self.repository.get_execution(execution_id)
        if execution is None:
            raise AiResourceNotFoundError("AiExecutionRun", execution_id)
        return AiExecutionRunResponse.model_validate(execution)


class AiExecutionCoordinator:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        provider: AiProvider,
        options: AiExecutionOptions,
        input_schemas: Mapping[tuple[str, int], type[BaseModel]],
        output_schemas: Mapping[tuple[str, int], type[BaseModel]],
        *,
        clock: Callable[[], datetime] | None = None,
        request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.options = options
        self.input_schemas = input_schemas
        self.output_schemas = output_schemas
        self.clock = clock or (lambda: datetime.now(UTC))
        self.request_id_factory = request_id_factory or (lambda: str(uuid.uuid4()))
        self.provider_key = _validate_provider_key(provider)

    def execute(
        self, prompt_version_id: int, input_value: Mapping[str, Any]
    ) -> AiExecutionRunResponse:
        with self.session_factory() as read_session:
            prompt = AiRepository(read_session).get_prompt_version(prompt_version_id)
            if prompt is None:
                raise AiResourceNotFoundError("AiPromptVersion", prompt_version_id)
            snapshot = _copy_prompt(prompt)

        input_model = self.input_schemas.get(
            (snapshot.input_schema_key, snapshot.input_schema_version)
        )
        output_model = self.output_schemas.get(
            (snapshot.output_schema_key, snapshot.output_schema_version)
        )
        if input_model is None or output_model is None:
            raise AiExecutionRejectedError("AI_PROMPT_RENDER_INVALID")
        try:
            validated_input = input_model.model_validate(input_value, strict=True)
            input_json = validated_input.model_dump(mode="json")
            canonical_input = canonical_json(input_json)
            system_prompt = _render(snapshot.system_template, input_json)
            user_prompt = _render(snapshot.user_template, input_json)
        except (ValidationError, ValueError, KeyError, TypeError):
            raise AiExecutionRejectedError("AI_PROMPT_RENDER_INVALID") from None

        if not self.options.model_id or (
            self.options.allowed_models
            and self.options.model_id not in self.options.allowed_models
        ):
            raise AiExecutionRejectedError("AI_MODEL_NOT_ALLOWED")

        request_id = self.request_id_factory()
        validate_ai_request_id(request_id)
        request = AiProviderRequest(
            request_id=request_id,
            model_id=self.options.model_id,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_model.model_json_schema(),
            timeout_seconds=self.options.timeout_seconds,
            max_output_tokens=self.options.max_output_tokens,
            temperature=self.options.temperature,
        )
        started_at = self.clock()
        result: AiProviderResult | None = None
        error_code: str | None = None
        output_json: dict[str, Any] | None = None
        output_hash: str | None = None
        try:
            raw_result = self.provider.generate(request)
        except AiProviderError as error:
            error_code = _provider_error_code(error)
        except Exception:  # noqa: BLE001 -- provider boundary must suppress raw details
            error_code = "AI_PROVIDER_ERROR"
        else:
            result = _normalize_provider_result(raw_result)
            if result is None:
                error_code = "AI_PROVIDER_INVALID_RESPONSE"
            else:
                try:
                    parsed = json.loads(
                        result.output_text,
                        parse_constant=lambda _value: (_ for _ in ()).throw(
                            ValueError()
                        ),
                    )
                except Exception:  # noqa: BLE001 -- provider JSON is untrusted
                    error_code = "AI_OUTPUT_INVALID_JSON"
                else:
                    try:
                        validated_output = output_model.model_validate(
                            parsed, strict=True
                        )
                        normalized_output = validated_output.model_dump(mode="json")
                        normalized_hash = sha256_text(
                            canonical_json(normalized_output)
                        )
                    except Exception:  # noqa: BLE001 -- provider output is untrusted
                        error_code = "AI_OUTPUT_SCHEMA_INVALID"
                        output_json = None
                        output_hash = None
                    else:
                        output_json = normalized_output
                        output_hash = normalized_hash
        completed_at = self.clock()

        with self.session_factory() as write_session:
            repository = AiRepository(write_session)
            if (
                repository.get_prompt_version_exact(
                    snapshot.id,
                    snapshot.prompt_key,
                    snapshot.version,
                    snapshot.checksum,
                )
                is None
            ):
                raise AiExecutionRejectedError("AI_PROMPT_VERSION_CHANGED")

            execution = AiExecutionRun(
                ai_prompt_version_id=snapshot.id,
                prompt_key=snapshot.prompt_key,
                prompt_version=snapshot.version,
                prompt_checksum=snapshot.checksum,
                provider_key=self.provider_key,
                model_id=self.options.model_id,
                request_id=request_id,
                status="FAILED" if error_code else "SUCCEEDED",
                input_json=input_json,
                input_sha256=sha256_text(canonical_input),
                rendered_system_sha256=sha256_text(system_prompt),
                rendered_user_sha256=sha256_text(user_prompt),
                output_json=output_json,
                output_sha256=output_hash,
                error_code=error_code,
                provider_request_id=(
                    _bounded(result.provider_request_id, 200) if result else None
                ),
                started_at=started_at,
                completed_at=completed_at,
                duration_ms=max(
                    0, int((completed_at - started_at).total_seconds() * 1000)
                ),
                input_tokens=result.input_tokens if result else None,
                output_tokens=result.output_tokens if result else None,
                total_tokens=result.total_tokens if result else None,
                provider_cost=_cost(result.provider_cost) if result else None,
                cost_currency=result.cost_currency if result else None,
                finish_reason=_bounded(result.finish_reason, 100) if result else None,
                safety_metadata=(
                    _bounded_metadata(result.safety_metadata) if result else None
                ),
            )
            try:
                repository.add_execution(execution)
                response = AiExecutionRunResponse.model_validate(execution)
                write_session.commit()
            except Exception:
                write_session.rollback()
                raise
        return response


def _copy_prompt(prompt: AiPromptVersion) -> _PromptSnapshot:
    return _PromptSnapshot(
        id=prompt.id,
        prompt_key=prompt.prompt_key,
        version=prompt.version,
        system_template=prompt.system_template,
        user_template=prompt.user_template,
        input_schema_key=prompt.input_schema_key,
        input_schema_version=prompt.input_schema_version,
        output_schema_key=prompt.output_schema_key,
        output_schema_version=prompt.output_schema_version,
        checksum=prompt.checksum,
    )


def _render(template: str, values: Mapping[str, Any]) -> str:
    formatter = string.Formatter()
    fields: set[str] = set()
    for _, field_name, format_spec, conversion in formatter.parse(template):
        if field_name is None:
            continue
        if (
            not field_name
            or format_spec
            or conversion
            or any(character in field_name for character in ".[]")
        ):
            raise ValueError("unsupported template placeholder")
        fields.add(field_name)
    if not fields.issubset(values):
        raise KeyError("missing template placeholder")
    rendered_values = {
        key: value if isinstance(value, str) else canonical_json(value)
        for key, value in values.items()
    }
    return template.format_map(rendered_values)


def validate_ai_request_id(value: str) -> None:
    if (
        type(value) is not str
        or not 1 <= len(value) <= 100
        or value != value.strip()
        or any(character.isspace() and character != " " for character in value)
        or any(
            ord(character) < 32 or 127 <= ord(character) <= 159
            for character in value
        )
    ):
        raise ValueError("AI request identity is invalid")


def _bounded(value: str | None, limit: int) -> str | None:
    if value is None or type(value) is not str:
        return None
    normalized = "".join(c for c in value if 32 <= ord(c) < 127).strip()
    return normalized[:limit] or None


def _bounded_metadata(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None or type(value) is not dict:
        return None
    try:
        if not _metadata_tree_is_safe(value):
            return None
        canonical = canonical_json(value)
        normalized = json.loads(canonical)
        if type(normalized) is not dict:
            return None
        database_text = json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
        )
        if len(database_text.encode("utf-8")) > 3_500:
            return {"truncated": True}
    except Exception:  # noqa: BLE001 -- optional provider metadata is untrusted
        return None
    return normalized


def _metadata_tree_is_safe(value: object) -> bool:
    nodes: list[tuple[object, int]] = [(value, 0)]
    visited = 0
    while nodes:
        item, depth = nodes.pop()
        visited += 1
        if visited > 1_000 or depth > 20:
            return False
        if item is None or type(item) in (bool, int):
            continue
        if type(item) is str:
            if "\x00" in item:
                return False
            continue
        if type(item) is list:
            nodes.extend((child, depth + 1) for child in item)
            continue
        if type(item) is dict:
            for key, child in item.items():
                if type(key) is not str or "\x00" in key:
                    return False
                nodes.append((child, depth + 1))
            continue
        return False
    return True


def _normalize_provider_result(value: object) -> AiProviderResult | None:
    try:
        if type(value) is not AiProviderResult:
            return None
        output_text = value.output_text
        provider_request_id = value.provider_request_id
        input_tokens = value.input_tokens
        output_tokens = value.output_tokens
        total_tokens = value.total_tokens
        provider_cost = value.provider_cost
        cost_currency = value.cost_currency
        finish_reason = value.finish_reason
        safety_metadata = value.safety_metadata
        if (
            type(output_text) is not str
            or not output_text.strip()
            or len(output_text) > _MAX_PROVIDER_OUTPUT_CHARACTERS
        ):
            return None
        counts = (input_tokens, output_tokens, total_tokens)
        if any(
            item is not None
            and (
                type(item) is not int
                or not 0 <= item <= _MAX_PROVIDER_TOKEN_COUNT
            )
            for item in counts
        ):
            return None
        if all(item is not None for item in counts) and total_tokens != (
            input_tokens + output_tokens
        ):
            return None
        if provider_request_id is not None and type(provider_request_id) is not str:
            return None
        if finish_reason is not None and type(finish_reason) is not str:
            return None
        if cost_currency is not None and (
            type(cost_currency) is not str
            or re.fullmatch(r"[A-Z]{3}", cost_currency) is None
        ):
            return None
        if (provider_cost is None) != (cost_currency is None):
            return None
        if provider_cost is not None and _cost(provider_cost) is None:
            return None
        return AiProviderResult(
            output_text=output_text,
            provider_request_id=_bounded(provider_request_id, 200),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider_cost=provider_cost,
            cost_currency=cost_currency,
            finish_reason=_bounded(finish_reason, 100),
            safety_metadata=_bounded_metadata(safety_metadata),
        )
    except Exception:  # noqa: BLE001 -- provider result objects are untrusted
        return None


def _cost(value: str | None) -> Decimal | None:
    if (
        value is None
        or type(value) is not str
        or _PROVIDER_COST_PATTERN.fullmatch(value) is None
    ):
        return None
    try:
        cost = Decimal(value)
    except (InvalidOperation, ValueError):
        return None
    return cost if cost.is_finite() and 0 <= cost < _MAX_PROVIDER_COST else None


def _provider_error_code(error: AiProviderError) -> str:
    try:
        code = error.error_code
    except Exception:  # noqa: BLE001 -- provider exceptions are untrusted
        return "AI_PROVIDER_ERROR"
    if (
        type(code) is not str
        or code not in _PROVIDER_ERROR_CODES
    ):
        return "AI_PROVIDER_ERROR"
    return code


def _validate_provider_key(provider: AiProvider) -> str:
    try:
        key = provider.key
    except Exception:  # noqa: BLE001 -- provider implementations are untrusted
        raise ValueError("AI provider key is invalid") from None
    if (
        type(key) is not str
        or not 1 <= len(key) <= 50
        or _PROVIDER_KEY_PATTERN.fullmatch(key) is None
    ):
        raise ValueError("AI provider key is invalid")
    return key


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)
