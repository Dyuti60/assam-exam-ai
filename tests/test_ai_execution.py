import json
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from enum import Enum
from math import inf, nan
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Text, delete, event, func, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import (
    AI_MAX_OUTPUT_TOKENS_LIMIT,
    AI_MODEL_IDENTIFIER_MAX_LENGTH,
    AI_REQUEST_TIMEOUT_MAX_SECONDS,
    Settings,
)
from app.core.database import engine, get_db
from app.main import app
from app.models import AiExecutionRun, AiPromptVersion, SourceChunk
from app.repositories.ai import AiRepository
from app.schemas.ai import AiPromptVersionCreate
from app.services.ai import (
    AiExecutionCoordinator,
    AiExecutionOptions,
    AiExecutionRejectedError,
    AiPromptService,
    AiProviderError,
    AiProviderRequest,
    AiProviderResult,
    AiResourceConflictError,
    AiResourceNotFoundError,
    canonical_json,
    prompt_checksum,
    sha256_text,
    validate_ai_request_id,
)
from app.services.gemini import GeminiProvider, _map_api_error


class InputContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str
    count: int


class OutputContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str
    score: int


class NonFiniteOutputContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float


class MalformedUsage:
    prompt_token_count = -1
    candidates_token_count = "three"
    total_token_count = -4


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    if not (engine.url.database or "").endswith("_test"):
        pytest.fail("AI execution tests require a dedicated *_test database")
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture
def client(db_connection: Connection) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        with Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _prompt_payload() -> dict:
    return {
        "prompt_key": "test.structured",
        "version": 1,
        "system_template": "Answer about {topic}.",
        "user_template": "Return {count} facts for {topic}.",
        "input_schema_key": "test.input",
        "input_schema_version": 1,
        "output_schema_key": "test.output",
        "output_schema_version": 1,
    }


def _create_prompt(client: TestClient) -> dict:
    response = client.post("/api/v1/ai-prompt-versions", json=_prompt_payload())
    assert response.status_code == 201, response.text
    return response.json()


class FakeProvider:
    key = "fake"

    def __init__(
        self,
        result: AiProviderResult | None = None,
        error_code: str | None = None,
        session: Session | None = None,
        before_generate: Callable[[], None] | None = None,
    ) -> None:
        self.result = result or AiProviderResult('{"score":2,"answer":"ok"}')
        self.error_code = error_code
        self.session = session
        self.before_generate = before_generate
        self.calls: list[AiProviderRequest] = []

    def generate(self, request: AiProviderRequest) -> AiProviderResult:
        assert self.session is None or not self.session.in_transaction()
        if self.before_generate is not None:
            self.before_generate()
        self.calls.append(request)
        if self.error_code:
            raise AiProviderError(self.error_code)
        return self.result


class TrackingSessionFactory:
    def __init__(
        self, bind: Connection | Engine, *, close_resets_only: bool = False
    ) -> None:
        self.bind = bind
        self.close_resets_only = close_resets_only
        self.sessions: list[Session] = []
        self.open_sessions = 0
        self.commit_count = 0
        self.rollback_count = 0

    def __call__(self) -> Session:
        factory = self

        class TrackedSession(Session):
            def commit(self) -> None:
                super().commit()
                factory.commit_count += 1

            def rollback(self) -> None:
                factory.rollback_count += 1
                super().rollback()

            def close(self) -> None:
                try:
                    super().close()
                finally:
                    factory.open_sessions -= 1

        session = TrackedSession(
            bind=self.bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
            close_resets_only=self.close_resets_only,
        )
        self.sessions.append(session)
        self.open_sessions += 1
        return session


def _coordinator(
    session_or_factory: Session | Callable[[], Session],
    provider: FakeProvider | GeminiProvider,
    *,
    model: str = "models/test-model",
    allowed: frozenset[str] = frozenset(),
    output_model: type[BaseModel] = OutputContract,
) -> AiExecutionCoordinator:
    times = iter(
        [
            datetime(2026, 9, 12, 5, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 5, 0, 0, 125000, tzinfo=UTC),
        ]
    )
    if isinstance(session_or_factory, Session):
        bind = session_or_factory.get_bind()
        session_factory = lambda: Session(
            bind=bind,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
    else:
        session_factory = session_or_factory
    return AiExecutionCoordinator(
        session_factory,
        provider,
        AiExecutionOptions(model, 7.5, 321, 0.0, allowed),
        {("test.input", 1): InputContract},
        {("test.output", 1): output_model},
        clock=lambda: next(times),
        request_id_factory=lambda: "00000000-0000-4000-8000-000000000001",
    )


def test_prompt_create_read_checksum_duplicate_and_closed_schema(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    assert prompt["checksum"] == prompt_checksum(_prompt_payload())
    assert prompt["created_at"]
    assert client.get(f"/api/v1/ai-prompt-versions/{prompt['id']}").json() == prompt
    duplicate = client.post("/api/v1/ai-prompt-versions", json=_prompt_payload())
    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "AiPromptVersion test.structured version 1 already exists"
    }
    invalid = client.post(
        "/api/v1/ai-prompt-versions", json={**_prompt_payload(), "checksum": "0" * 64}
    )
    assert invalid.status_code == 422
    assert client.get("/api/v1/ai-prompt-versions/999999").json() == {
        "detail": "AiPromptVersion 999999 not found"
    }
    assert db_connection.scalar(select(func.count()).select_from(AiPromptVersion)) == 1


@pytest.mark.parametrize(
    "field",
    ["version", "input_schema_version", "output_schema_version"],
)
def test_prompt_integer_contract_fields_reject_boolean_and_string_coercion(
    client: TestClient, db_connection: Connection, field: str
) -> None:
    for value in (True, "1"):
        response = client.post(
            "/api/v1/ai-prompt-versions",
            json={**_prompt_payload(), field: value},
        )
        assert response.status_code == 422
    assert db_connection.scalar(select(func.count()).select_from(AiPromptVersion)) == 0


def test_canonical_json_and_prompt_hashes_are_stable_and_change_sensitive() -> None:
    first = {"z": [1, 2], "nested": {"b": "অসম", "a": True}}
    reordered = {"nested": {"a": True, "b": "অসম"}, "z": [1, 2]}
    reordered_array = {"nested": {"a": True, "b": "অসম"}, "z": [2, 1]}

    assert canonical_json(first) == canonical_json(reordered)
    assert canonical_json(first) == '{"nested":{"a":true,"b":"অসম"},"z":[1,2]}'
    assert sha256_text(canonical_json(first)) == sha256_text(canonical_json(reordered))
    assert sha256_text(canonical_json(first)) != sha256_text(
        canonical_json(reordered_array)
    )
    assert "অসম" in canonical_json(first)

    prompt = _prompt_payload()
    changed_text = {**prompt, "user_template": "Return {count} verified facts."}
    changed_schema = {**prompt, "output_schema_version": 2}
    assert prompt_checksum(prompt) != prompt_checksum(changed_text)
    assert prompt_checksum(prompt) != prompt_checksum(changed_schema)


def test_prompt_versions_have_no_mutation_boundary_and_execution_keeps_snapshot(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    for method in (client.put, client.patch):
        response = method(
            f"/api/v1/ai-prompt-versions/{prompt['id']}",
            json={"user_template": "changed"},
        )
        assert response.status_code == 405
    assert not hasattr(AiRepository, "update_prompt_version")
    assert not hasattr(AiPromptService, "update")
    assert client.get(f"/api/v1/ai-prompt-versions/{prompt['id']}").json() == prompt

    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        execution = _coordinator(session, FakeProvider()).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    assert execution.ai_prompt_version_id == prompt["id"]
    assert execution.prompt_key == prompt["prompt_key"]
    assert execution.prompt_version == prompt["version"]
    assert execution.prompt_checksum == prompt["checksum"]
    assert client.get(f"/api/v1/ai-prompt-versions/{prompt['id']}").json() == prompt


def test_concurrent_prompt_creation_uses_named_database_uniqueness() -> None:
    prompt_key = f"test.concurrent.{uuid4().hex}"
    payload = {**_prompt_payload(), "prompt_key": prompt_key}
    barrier = Barrier(2)

    def create() -> tuple[str, str | None]:
        with Session(engine, expire_on_commit=False) as session:
            barrier.wait()
            try:
                result = AiPromptService(session).create(
                    AiPromptVersionCreate(**payload)
                )
            except AiResourceConflictError as error:
                return "conflict", str(error)
            return "created", str(result.id)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _value: create(), range(2)))
        assert sorted(outcome[0] for outcome in outcomes) == ["conflict", "created"]
        assert [outcome[1] for outcome in outcomes if outcome[0] == "conflict"] == [
            f"AiPromptVersion {prompt_key} version 1 already exists"
        ]
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(AiPromptVersion)
                    .where(
                        AiPromptVersion.prompt_key == prompt_key,
                        AiPromptVersion.version == 1,
                    )
                )
                == 1
            )
            with pytest.raises(IntegrityError) as raised, connection.begin_nested():
                connection.execute(
                    AiPromptVersion.__table__.insert().values(
                        **payload, checksum=prompt_checksum(payload)
                    )
                )
            assert raised.value.orig.diag.constraint_name == (
                "uq_ai_prompt_versions_key_version"
            )
    finally:
        with engine.begin() as connection:
            connection.execute(
                delete(AiPromptVersion).where(AiPromptVersion.prompt_key == prompt_key)
            )


@pytest.mark.parametrize(
    ("field", "value", "valid"),
    [
        ("ai_request_timeout_seconds", 0, False),
        ("ai_request_timeout_seconds", -1, False),
        ("ai_request_timeout_seconds", AI_REQUEST_TIMEOUT_MAX_SECONDS, True),
        ("ai_request_timeout_seconds", AI_REQUEST_TIMEOUT_MAX_SECONDS + 0.1, False),
        ("ai_max_output_tokens", 0, False),
        ("ai_max_output_tokens", -1, False),
        ("ai_max_output_tokens", AI_MAX_OUTPUT_TOKENS_LIMIT, True),
        ("ai_max_output_tokens", AI_MAX_OUTPUT_TOKENS_LIMIT + 1, False),
        ("ai_temperature", -0.1, False),
        ("ai_temperature", 0, True),
        ("ai_temperature", 2, True),
        ("ai_temperature", 2.1, False),
    ],
)
def test_ai_numeric_settings_are_bounded(
    field: str, value: object, valid: bool
) -> None:
    values = {"database_url": "postgresql+psycopg://localhost/test", field: value}
    if valid:
        assert getattr(Settings(**values), field) == value
    else:
        with pytest.raises(ValueError):
            Settings(**values)


@pytest.mark.parametrize(
    ("field", "option_index", "invalid_values"),
    [
        (
            "ai_request_timeout_seconds",
            1,
            [
                True,
                False,
                0,
                -1,
                AI_REQUEST_TIMEOUT_MAX_SECONDS + 0.1,
                nan,
                inf,
                -inf,
                " 30",
                "30 ",
                "3_0",
                "0x1e",
                "credential-timeout",
            ],
        ),
        (
            "ai_max_output_tokens",
            2,
            [
                True,
                False,
                0,
                -1,
                AI_MAX_OUTPUT_TOKENS_LIMIT + 1,
                nan,
                inf,
                -inf,
                " 2048",
                "2048 ",
                "2_048",
                "0x800",
                "credential-tokens",
            ],
        ),
        (
            "ai_temperature",
            3,
            [
                True,
                False,
                -0.1,
                2.1,
                nan,
                inf,
                -inf,
                " 0",
                "0 ",
                "0_0",
                "0x0",
                "credential-temperature",
            ],
        ),
    ],
)
def test_ai_numeric_settings_and_options_reject_the_same_invalid_values(
    field: str, option_index: int, invalid_values: list[object]
) -> None:
    for value in invalid_values:
        with pytest.raises(ValueError) as settings_error:
            Settings(
                _env_file=None,
                database_url="postgresql+psycopg://localhost/test",
                **{field: value},
            )
        options: list[object] = ["model", 30, 2048, 0]
        options[option_index] = value
        with pytest.raises(ValueError) as options_error:
            AiExecutionOptions(*options)
        assert "credential-" not in str(settings_error.value)
        assert "credential-" not in str(options_error.value)


@pytest.mark.parametrize(
    ("field", "option_index", "valid_values"),
    [
        ("ai_request_timeout_seconds", 1, [30, 7.5, AI_REQUEST_TIMEOUT_MAX_SECONDS]),
        ("ai_max_output_tokens", 2, [2048, AI_MAX_OUTPUT_TOKENS_LIMIT]),
        ("ai_temperature", 3, [0, 2]),
    ],
)
def test_ai_numeric_settings_and_options_accept_the_same_valid_values(
    field: str, option_index: int, valid_values: list[object]
) -> None:
    for value in valid_values:
        configured = Settings(
            _env_file=None,
            database_url="postgresql+psycopg://localhost/test",
            **{field: value},
        )
        options: list[object] = ["model", 30, 2048, 0]
        options[option_index] = value
        execution_options = AiExecutionOptions(*options)
        option_field = (
            "model_id",
            "timeout_seconds",
            "max_output_tokens",
            "temperature",
        )[option_index]
        assert getattr(configured, field) == value
        assert getattr(execution_options, option_field) == value


def test_ai_numeric_environment_strings_are_validated_and_normalized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AI_REQUEST_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("AI_MAX_OUTPUT_TOKENS", "2048")
    monkeypatch.setenv("AI_TEMPERATURE", "0")
    configured = Settings(
        _env_file=None, database_url="postgresql+psycopg://localhost/test"
    )
    assert configured.ai_request_timeout_seconds == 30.0
    assert configured.ai_max_output_tokens == 2048
    assert configured.ai_temperature == 0.0


@pytest.mark.parametrize("hostile_type", [int, float, str])
def test_ai_numeric_subclasses_are_rejected_without_conversion(
    hostile_type: type,
) -> None:
    class HostileNumber(hostile_type):
        def __str__(self) -> str:
            raise LookupError("credential-number-detail")

    value = HostileNumber("1") if hostile_type is str else HostileNumber(1)
    with pytest.raises(ValueError) as settings_error:
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://localhost/test",
            ai_request_timeout_seconds=value,
        )
    with pytest.raises(ValueError) as options_error:
        AiExecutionOptions("model", value, 1, 0)
    assert "credential-number-detail" not in str(settings_error.value)
    assert "credential-number-detail" not in str(options_error.value)


@pytest.mark.parametrize(
    ("model", "valid"),
    [
        ("", True),
        ("gemini-2.5-flash", True),
        ("models/gemini-2.5_flash:stable", True),
        ("a" * AI_MODEL_IDENTIFIER_MAX_LENGTH, True),
        ("a" * (AI_MODEL_IDENTIFIER_MAX_LENGTH + 1), False),
        (" gemini-2.5-flash", False),
        ("gemini-2.5-flash ", False),
        ("gemini 2.5", False),
        ("gemini\n2.5", False),
        ("gemini@latest", False),
    ],
)
def test_ai_model_setting_is_blank_safe_and_strict(model: str, valid: bool) -> None:
    values = {
        "database_url": "postgresql+psycopg://localhost/test",
        "gemini_model": model,
    }
    if valid:
        assert Settings(**values).gemini_model == model
    else:
        with pytest.raises(ValueError):
            Settings(**values)


@pytest.mark.parametrize(
    "options",
    [
        (" model", 1, 1, 0),
        ("model", 0, 1, 0),
        ("model", -1, 1, 0),
        ("model", AI_REQUEST_TIMEOUT_MAX_SECONDS + 1, 1, 0),
        ("model", 1, 0, 0),
        ("model", 1, -1, 0),
        ("model", 1, AI_MAX_OUTPUT_TOKENS_LIMIT + 1, 0),
        ("model", 1, 1, -0.1),
        ("model", 1, 1, 2.1),
        ("model", 1, 1, nan),
    ],
)
def test_ai_execution_options_reject_bypass_attempts(
    options: tuple[str, float, int, float],
) -> None:
    with pytest.raises(ValueError):
        AiExecutionOptions(*options)


def test_ai_execution_options_accept_exact_bounds_and_valid_model() -> None:
    options = AiExecutionOptions(
        "models/gemini-2.5_flash:stable",
        AI_REQUEST_TIMEOUT_MAX_SECONDS,
        AI_MAX_OUTPUT_TOKENS_LIMIT,
        2,
        {"models/gemini-2.5_flash:stable"},
    )
    assert options.timeout_seconds == AI_REQUEST_TIMEOUT_MAX_SECONDS
    assert options.max_output_tokens == AI_MAX_OUTPUT_TOKENS_LIMIT
    assert options.temperature == 2
    assert options.allowed_models == frozenset({options.model_id})


@pytest.mark.parametrize(
    "request_id",
    [
        "",
        " ",
        "  ",
        "\t",
        "\n",
        "\r",
        " leading",
        "trailing ",
        "x\x00y",
        "x\x1fy",
        "x\x7fy",
        "x\x80y",
        "x" * 101,
    ],
)
def test_request_identity_application_validation_rejects_unsafe_values(
    request_id: str,
) -> None:
    with pytest.raises(ValueError, match="AI request identity is invalid"):
        validate_ai_request_id(request_id)


@pytest.mark.parametrize("request_id", ["x", "x" * 100, "request id", str(uuid4())])
def test_request_identity_application_validation_accepts_safe_boundaries(
    request_id: str,
) -> None:
    validate_ai_request_id(request_id)


def test_request_identity_rejects_string_subclass_without_invoking_it() -> None:
    class HostileRequestId(str):
        def strip(self, _characters=None):
            raise LookupError("credential-request-id")

    with pytest.raises(ValueError, match="AI request identity is invalid") as raised:
        validate_ai_request_id(HostileRequestId("request-id"))
    assert "credential-request-id" not in str(raised.value)


def test_invalid_request_identity_stops_before_provider_and_persistence(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection, close_resets_only=False)
    provider = FakeProvider()
    coordinator = AiExecutionCoordinator(
        session_factory,
        provider,
        AiExecutionOptions("models/test", 1, 10, 0),
        {("test.input", 1): InputContract},
        {("test.output", 1): OutputContract},
        request_id_factory=lambda: " invalid ",
    )
    with pytest.raises(ValueError, match="AI request identity is invalid"):
        coordinator.execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert provider.calls == []
    assert session_factory.commit_count == 0
    assert session_factory.open_sessions == 0
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0


def test_invalid_options_fail_before_provider_or_execution(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    provider = FakeProvider()
    invalid_options = [
        ("model", True, 1, 0),
        ("model", 1, True, 0),
        ("model", 1, 1, True),
        ("model", 1, AI_MAX_OUTPUT_TOKENS_LIMIT + 1, 0),
    ]
    for values in invalid_options:
        with pytest.raises(ValueError):
            AiExecutionOptions(*values)
    assert provider.calls == []
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0

    with pytest.raises(AiExecutionRejectedError, match="^AI_MODEL_NOT_ALLOWED$"):
        AiExecutionCoordinator(
            lambda: Session(
                bind=db_connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ),
            provider,
            AiExecutionOptions("", 1, 1, 0),
            {("test.input", 1): InputContract},
            {("test.output", 1): OutputContract},
        ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert provider.calls == []
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0


def test_coordinator_success_records_canonical_audit_and_retrieval_is_stable(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection)
    provider = FakeProvider(
        AiProviderResult(
            '{"score":2,"answer":"ok"}',
            provider_request_id="provider-1",
            input_tokens=3,
            output_tokens=4,
            total_tokens=7,
            finish_reason="STOP",
            safety_metadata={"blocked": False},
        ),
        before_generate=lambda: (
            session_factory.open_sessions == 0
            or pytest.fail("database session open during provider I/O")
        ),
    )
    result = _coordinator(session_factory, provider).execute(
        prompt["id"], {"count": 2, "topic": "Assam"}
    )

    assert len(provider.calls) == 1
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert session_factory.open_sessions == 0
    assert len(session_factory.sessions) == 2
    assert all(not session.in_transaction() for session in session_factory.sessions)
    request = provider.calls[0]
    assert request.model_id == "models/test-model"
    assert request.system_prompt == "Answer about Assam."
    assert request.user_prompt == "Return 2 facts for Assam."
    assert request.timeout_seconds == 7.5
    assert request.max_output_tokens == 321
    assert request.temperature == 0
    assert request.output_schema["additionalProperties"] is False
    expected_input = {"count": 2, "topic": "Assam"}
    expected_output = {"answer": "ok", "score": 2}
    assert result.status == "SUCCEEDED"
    assert result.input_json == expected_input
    assert result.input_sha256 == sha256_text(canonical_json(expected_input))
    assert result.rendered_system_sha256 == sha256_text(request.system_prompt)
    assert result.rendered_user_sha256 == sha256_text(request.user_prompt)
    assert result.output_json == expected_output
    assert result.output_sha256 == sha256_text(canonical_json(expected_output))
    assert result.error_code is None
    assert result.duration_ms == 125
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (3, 4, 7)
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 1
    first = client.get(f"/api/v1/ai-execution-runs/{result.id}")
    second = client.get(f"/api/v1/ai-execution-runs/{result.id}")
    assert first.status_code == 200
    assert first.json() == second.json()
    assert first.json()["request_id"] == result.request_id
    assert client.get("/api/v1/ai-execution-runs/999999").json() == {
        "detail": "AiExecutionRun 999999 not found"
    }


@pytest.mark.parametrize(
    "error_code",
    [
        "AI_PROVIDER_DISABLED",
        "AI_PROVIDER_AUTHENTICATION",
        "AI_PROVIDER_RATE_LIMITED",
        "AI_PROVIDER_TIMEOUT",
        "AI_PROVIDER_SAFETY_BLOCKED",
        "AI_PROVIDER_UNAVAILABLE",
        "AI_PROVIDER_TRANSPORT",
        "AI_PROVIDER_INVALID_RESPONSE",
        "AI_PROVIDER_RESPONSE_INVALID",
    ],
)
def test_provider_failures_create_one_sanitized_terminal_audit(
    client: TestClient, db_connection: Connection, error_code: str
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection)
    provider = FakeProvider(
        error_code=error_code,
        before_generate=lambda: (
            session_factory.open_sessions == 0
            or pytest.fail("database session open during provider I/O")
        ),
    )
    result = _coordinator(session_factory, provider).execute(
        prompt["id"], {"topic": "Assam", "count": 1}
    )
    assert len(provider.calls) == 1
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert session_factory.open_sessions == 0
    assert result.status == "FAILED"
    assert result.error_code == error_code
    assert result.output_json is None
    assert result.output_sha256 is None
    assert result.provider_request_id is None
    assert result.finish_reason is None
    assert result.safety_metadata is None
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 1


def test_ordinary_provider_exception_becomes_one_sanitized_failed_audit(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection, close_resets_only=False)
    secret_detail = "fake-api-key credential header upstream-body"

    class FailingProvider(FakeProvider):
        def generate(self, request: AiProviderRequest) -> AiProviderResult:
            assert session_factory.open_sessions == 0
            self.calls.append(request)
            raise LookupError(secret_detail)

    provider = FailingProvider()
    result = _coordinator(session_factory, provider).execute(
        prompt["id"], {"topic": "Assam", "count": 1}
    )
    serialized = result.model_dump_json()
    assert len(provider.calls) == 1
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert session_factory.open_sessions == 0
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_ERROR"
    assert result.output_json is None
    assert result.output_sha256 is None
    assert secret_detail not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("output_text", type("HostileText", (str,), {})("{\"answer\":\"ok\",\"score\":2}")),
        ("provider_request_id", type("HostileRequestId", (str,), {})("request")),
        ("input_tokens", type("HostileInputTokens", (int,), {})(1)),
        ("output_tokens", type("HostileOutputTokens", (int,), {})(1)),
        ("total_tokens", type("HostileTotalTokens", (int,), {})(2)),
        ("provider_cost", type("HostileCost", (str,), {})("0.1")),
        ("cost_currency", type("HostileCurrency", (str,), {})("USD")),
        ("finish_reason", type("HostileFinish", (str,), {})("STOP")),
    ],
)
def test_provider_scalar_subclasses_cannot_cross_coordinator_boundary(
    client: TestClient,
    db_connection: Connection,
    field: str,
    value: object,
) -> None:
    prompt = _create_prompt(client)
    provider_result = AiProviderResult(
        '{"answer":"ok","score":2}',
        input_tokens=1,
        output_tokens=1,
        total_tokens=2,
        provider_cost="0.1",
        cost_currency="USD",
    )
    object.__setattr__(provider_result, field, value)
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(provider_result),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_INVALID_RESPONSE"
    assert result.output_json is None
    assert result.output_sha256 is None
    assert result.provider_request_id is None
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )


@pytest.mark.parametrize(
    "provider_cost", ["1000000000000", "0.0000001", "01.00", "1e2"]
)
def test_unrepresentable_provider_cost_cannot_reach_postgresql(
    client: TestClient,
    db_connection: Connection,
    provider_cost: str,
) -> None:
    prompt = _create_prompt(client)
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(
            AiProviderResult(
                '{"answer":"ok","score":2}',
                provider_cost=provider_cost,
                cost_currency="USD",
            )
        ),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_INVALID_RESPONSE"
    assert result.provider_cost is None
    assert result.cost_currency is None


def test_hostile_optional_metadata_is_omitted_without_execution_failure(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)

    class HostileMetadata(dict):
        def __iter__(self):
            raise LookupError("fake-api-key hostile-metadata")

    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(
            AiProviderResult(
                '{"answer":"ok","score":2}',
                safety_metadata=HostileMetadata(secret="fake-api-key"),
            )
        ),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "SUCCEEDED"
    assert result.safety_metadata is None
    assert "fake-api-key" not in result.model_dump_json()


def test_metadata_bound_accounts_for_postgresql_jsonb_rendering(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    metadata = {f"{index:03}": 0 for index in range(410)}
    assert len(canonical_json(metadata).encode("utf-8")) == 3_281
    assert len(json.dumps(metadata, sort_keys=True).encode("utf-8")) == 4_100
    session_factory = TrackingSessionFactory(db_connection)
    provider = FakeProvider(
        AiProviderResult(
            '{"answer":"ok","score":2}',
            safety_metadata=metadata,
        )
    )

    result = _coordinator(session_factory, provider).execute(
        prompt["id"], {"topic": "Assam", "count": 1}
    )

    assert len(provider.calls) == 1
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert result.status == "SUCCEEDED"
    assert result.safety_metadata == {"truncated": True}
    stored_size = db_connection.scalar(
        select(func.octet_length(AiExecutionRun.safety_metadata.cast(Text))).where(
            AiExecutionRun.id == result.id
        )
    )
    assert stored_size is not None and stored_size <= 4_000


def test_hostile_provider_error_code_is_sanitized_before_persistence(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)

    class HostileCode(str):
        def __str__(self) -> str:
            raise LookupError("fake-api-key hostile-code")

    class FailingProvider(FakeProvider):
        def generate(self, request: AiProviderRequest) -> AiProviderResult:
            self.calls.append(request)
            raise AiProviderError(HostileCode("AI_PROVIDER_TIMEOUT"))

    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FailingProvider(),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_ERROR"
    assert "hostile-code" not in result.model_dump_json()


@pytest.mark.parametrize("key", ["", "Gemini", "gemini key", "g" * 51])
def test_invalid_provider_key_fails_before_session_or_provider_io(key: str) -> None:
    calls = 0
    sessions = 0

    class InvalidProvider:
        def __init__(self) -> None:
            self.key = key

        def generate(self, _request: AiProviderRequest) -> AiProviderResult:
            nonlocal calls
            calls += 1
            return AiProviderResult('{"answer":"ok","score":2}')

    def session_factory() -> Session:
        nonlocal sessions
        sessions += 1
        raise AssertionError("session factory must not run")

    with pytest.raises(ValueError, match="AI provider key is invalid"):
        AiExecutionCoordinator(
            session_factory,
            InvalidProvider(),
            AiExecutionOptions("model", 1, 1, 0),
            {},
            {},
        )
    assert calls == 0
    assert sessions == 0


@pytest.mark.parametrize(
    ("output", "error_code"),
    [
        ("not json", "AI_OUTPUT_INVALID_JSON"),
        ('{"answer":"ok"}', "AI_OUTPUT_SCHEMA_INVALID"),
        ('{"answer":"ok","score":"2"}', "AI_OUTPUT_SCHEMA_INVALID"),
        ('{"answer":"ok","score":2,"extra":true}', "AI_OUTPUT_SCHEMA_INVALID"),
    ],
)
def test_invalid_structured_outputs_are_failed_audits(
    client: TestClient, db_connection: Connection, output: str, error_code: str
) -> None:
    prompt = _create_prompt(client)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        result = _coordinator(session, FakeProvider(AiProviderResult(output))).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    assert result.status == "FAILED"
    assert result.error_code == error_code


def test_pathologically_nested_provider_json_is_a_sanitized_failed_audit(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    nested_json = "[" * 2_000 + "]" * 2_000
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(AiProviderResult(nested_json)),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_OUTPUT_SCHEMA_INVALID"
    assert result.output_json is None
    assert result.output_sha256 is None


def test_ordinary_json_parser_failure_is_a_sanitized_failed_audit(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = _create_prompt(client)

    def fail_parser(*_args: object, **_kwargs: object) -> None:
        raise LookupError("fake-api-key hostile-json-parser")

    monkeypatch.setattr("app.services.ai.json.loads", fail_parser)
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(AiProviderResult('{"answer":"ok","score":2}')),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_OUTPUT_INVALID_JSON"
    assert result.output_json is None
    assert "hostile-json-parser" not in result.model_dump_json()


def test_ordinary_schema_normalization_failure_is_a_sanitized_failed_audit(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt = _create_prompt(client)

    def fail_validation(*_args: object, **_kwargs: object) -> None:
        raise LookupError("fake-api-key hostile-schema-detail")

    monkeypatch.setattr(OutputContract, "model_validate", fail_validation)
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        FakeProvider(AiProviderResult('{"answer":"ok","score":2}')),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert result.status == "FAILED"
    assert result.error_code == "AI_OUTPUT_SCHEMA_INVALID"
    assert result.output_json is None
    assert "hostile-schema-detail" not in result.model_dump_json()


def test_canonicalization_failure_clears_partial_output_and_persists_failed_audit(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection)
    provider = FakeProvider(AiProviderResult('{"x":1e400}'))

    result = _coordinator(
        session_factory,
        provider,
        output_model=NonFiniteOutputContract,
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})

    assert len(provider.calls) == 1
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert session_factory.open_sessions == 0
    assert result.status == "FAILED"
    assert result.error_code == "AI_OUTPUT_SCHEMA_INVALID"
    assert result.output_json is None
    assert result.output_sha256 is None
    stored = db_connection.execute(
        select(
            AiExecutionRun.status,
            AiExecutionRun.output_json,
            AiExecutionRun.output_sha256,
        ).where(AiExecutionRun.id == result.id)
    ).one()
    assert stored == ("FAILED", None, None)


def test_render_input_and_model_failures_happen_before_provider_io(
    client: TestClient, db_connection: Connection
) -> None:
    valid_prompt = _create_prompt(client)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        provider = FakeProvider()
        with pytest.raises(ValueError, match="AI model is not allowed"):
            _coordinator(
                session,
                provider,
                allowed=frozenset({"models/allowed"}),
            ).execute(valid_prompt["id"], {"topic": "Assam", "count": 1})
        assert provider.calls == []

    payload = _prompt_payload()
    payload["prompt_key"] = "test.invalid-template"
    payload["user_template"] = "Unknown {missing}"
    response = client.post("/api/v1/ai-prompt-versions", json=payload)
    assert response.status_code == 201
    prompt_id = response.json()["id"]
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        provider = FakeProvider()
        with pytest.raises(AiExecutionRejectedError, match="AI_PROMPT_RENDER_INVALID"):
            _coordinator(session, provider).execute(
                prompt_id, {"topic": "Assam", "count": 1}
            )
        assert provider.calls == []
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0
    with pytest.raises(ValueError):
        canonical_json({"bad": nan})


def test_prompt_revalidation_detects_change_after_provider_io(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)

    class MutatingProvider(FakeProvider):
        def generate(self, request: AiProviderRequest) -> AiProviderResult:
            db_connection.execute(
                update(AiPromptVersion)
                .where(AiPromptVersion.id == prompt["id"])
                .values(checksum="f" * 64)
            )
            return super().generate(request)

    session_factory = TrackingSessionFactory(db_connection)
    with pytest.raises(AiExecutionRejectedError, match="AI_PROMPT_VERSION_CHANGED"):
        provider = MutatingProvider()
        _coordinator(session_factory, provider).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    assert len(provider.calls) == 1
    assert session_factory.open_sessions == 0
    assert session_factory.commit_count == 0
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0


def test_post_flush_failure_rolls_back_execution(
    client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = _create_prompt(client)
    session_factory = TrackingSessionFactory(db_connection)
    provider = FakeProvider()
    coordinator = _coordinator(session_factory, provider)
    original = AiRepository.add_execution

    def fail_after_flush(
        repository: AiRepository, execution: AiExecutionRun
    ) -> AiExecutionRun:
        original(repository, execution)
        raise RuntimeError("injected persistence failure")

    monkeypatch.setattr(AiRepository, "add_execution", fail_after_flush)
    with pytest.raises(RuntimeError, match="injected persistence failure"):
        coordinator.execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert len(coordinator.provider.calls) == 1
    assert session_factory.commit_count == 0
    assert session_factory.rollback_count == 1
    assert session_factory.open_sessions == 0
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0


def test_coordinator_owns_sessions_and_preserves_caller_unit_of_work(
    client: TestClient, db_connection: Connection
) -> None:
    target = _create_prompt(client)
    dirty_payload = {**_prompt_payload(), "prompt_key": "test.caller-dirty"}
    deleted_payload = {**_prompt_payload(), "prompt_key": "test.caller-deleted"}
    dirty = client.post("/api/v1/ai-prompt-versions", json=dirty_payload).json()
    deleted = client.post("/api/v1/ai-prompt-versions", json=deleted_payload).json()
    session_factory = TrackingSessionFactory(db_connection, close_resets_only=False)
    with Session(
        bind=db_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
        close_resets_only=False,
    ) as caller_session:
        dirty_row = caller_session.get(AiPromptVersion, dirty["id"])
        deleted_row = caller_session.get(AiPromptVersion, deleted["id"])
        assert dirty_row is not None and deleted_row is not None
        dirty_row.system_template = "caller-owned pending change"
        caller_session.delete(deleted_row)
        pending = AiPromptVersion(
            **{**_prompt_payload(), "prompt_key": "test.caller-pending"},
            checksum="0" * 64,
        )
        caller_session.add(pending)
        expected_new = set(caller_session.new)
        expected_dirty = set(caller_session.dirty)
        expected_deleted = set(caller_session.deleted)
        caller_transaction = caller_session.get_transaction()

        provider = FakeProvider(
            before_generate=lambda: (
                session_factory.open_sessions == 0
                or pytest.fail("database session open during provider I/O")
            )
        )
        result = _coordinator(session_factory, provider).execute(
            target["id"], {"topic": "Assam", "count": 1}
        )

        assert set(caller_session.new) == expected_new
        assert set(caller_session.dirty) == expected_dirty
        assert set(caller_session.deleted) == expected_deleted
        assert dirty_row.system_template == "caller-owned pending change"
        assert caller_session.is_active
        assert caller_session.get_transaction() is caller_transaction
        assert caller_session.get(AiPromptVersion, dirty["id"]) is dirty_row
    assert result.status == "SUCCEEDED"
    assert session_factory.open_sessions == 0
    assert len(session_factory.sessions) == 2


def test_coordinator_missing_prompt_closes_owned_session_without_provider_call(
    db_connection: Connection,
) -> None:
    session_factory = TrackingSessionFactory(db_connection, close_resets_only=False)
    provider = FakeProvider()
    with pytest.raises(
        AiResourceNotFoundError, match="AiPromptVersion 999999 not found"
    ):
        _coordinator(session_factory, provider).execute(
            999999, {"topic": "Assam", "count": 1}
        )
    assert provider.calls == []
    assert session_factory.open_sessions == 0
    assert len(session_factory.sessions) == 1
    assert session_factory.commit_count == 0
    assert db_connection.scalar(select(func.count()).select_from(AiExecutionRun)) == 0


def test_coordinator_returns_without_transaction_or_post_commit_reload(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement.lower())

    session_factory = TrackingSessionFactory(db_connection, close_resets_only=False)
    event.listen(db_connection, "before_cursor_execute", capture)
    try:
        result = _coordinator(session_factory, FakeProvider()).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    finally:
        event.remove(db_connection, "before_cursor_execute", capture)
    relevant = [
        statement
        for statement in statements
        if "ai_prompt_versions" in statement or "ai_execution_runs" in statement
    ]
    assert result.status == "SUCCEEDED"
    assert sum(statement.lstrip().startswith("select") for statement in relevant) == 2
    assert sum(statement.lstrip().startswith("insert") for statement in relevant) == 1
    assert relevant[-1].lstrip().startswith("insert")
    assert session_factory.open_sessions == 0
    assert all(not session.in_transaction() for session in session_factory.sessions)


def test_provider_io_has_no_coordinator_owned_connection_checked_out() -> None:
    if not (engine.url.database or "").endswith("_test"):
        pytest.fail("AI execution tests require a dedicated *_test database")
    payload = {
        **_prompt_payload(),
        "prompt_key": f"test.connection-boundary.{uuid4().hex}",
    }
    with Session(bind=engine, expire_on_commit=False) as seed_session:
        prompt = AiPromptService(seed_session).create(
            AiPromptVersionCreate.model_validate(payload)
        )

    checked_out = 0

    def checkout(_dbapi_connection, _connection_record, _connection_proxy) -> None:
        nonlocal checked_out
        checked_out += 1

    def checkin(_dbapi_connection, _connection_record) -> None:
        nonlocal checked_out
        checked_out -= 1

    session_factory = TrackingSessionFactory(engine, close_resets_only=False)
    provider = FakeProvider(
        before_generate=lambda: (
            checked_out == 0
            or pytest.fail("coordinator connection checked out during provider I/O")
        )
    )
    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)
    execution_id: int | None = None
    try:
        result = _coordinator(session_factory, provider).execute(
            prompt.id, {"topic": "Assam", "count": 1}
        )
        execution_id = result.id
        assert checked_out == 0
        assert session_factory.open_sessions == 0
    finally:
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)
        with Session(bind=engine) as cleanup_session:
            if execution_id is not None:
                cleanup_session.execute(
                    delete(AiExecutionRun).where(AiExecutionRun.id == execution_id)
                )
            cleanup_session.execute(
                delete(AiPromptVersion).where(AiPromptVersion.id == prompt.id)
            )
            cleanup_session.commit()


def test_database_constraints_and_prompt_restricted_deletion(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        execution = _coordinator(session, FakeProvider()).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    second_times = iter(
        [
            datetime(2026, 9, 12, 6, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 6, 0, 0, 1000, tzinfo=UTC),
        ]
    )
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        second = AiExecutionCoordinator(
            lambda: Session(
                bind=db_connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ),
            FakeProvider(),
            AiExecutionOptions("models/test", 1, 10, 0),
            {("test.input", 1): InputContract},
            {("test.output", 1): OutputContract},
            clock=lambda: next(second_times),
            request_id_factory=lambda: "second-request-id",
        ).execute(prompt["id"], {"topic": "Assam", "count": 1})

    prompt_values = _prompt_payload()
    with (
        pytest.raises(IntegrityError) as duplicate_prompt,
        db_connection.begin_nested(),
    ):
        db_connection.execute(
            AiPromptVersion.__table__.insert().values(
                **prompt_values, checksum=prompt_checksum(prompt_values)
            )
        )
    assert duplicate_prompt.value.orig.diag.constraint_name == (
        "uq_ai_prompt_versions_key_version"
    )

    invalid_prompt = {
        **prompt_values,
        "prompt_key": "test.invalid-checksum",
        "checksum": "A" * 64,
    }
    with pytest.raises(IntegrityError) as bad_prompt_hash, db_connection.begin_nested():
        db_connection.execute(
            AiPromptVersion.__table__.insert().values(**invalid_prompt)
        )
    assert bad_prompt_hash.value.orig.diag.constraint_name == (
        "ck_ai_prompt_versions_checksum"
    )

    invalid_updates = [
        {"status": "PENDING"},
        {"status": "FAILED", "error_code": None},
        {"output_json": None},
        {"completed_at": datetime(2026, 9, 12, 4, 59, tzinfo=UTC)},
        {"input_tokens": -1},
        {"output_tokens": -1},
        {"total_tokens": -1},
        {"input_tokens": 1, "output_tokens": 1, "total_tokens": 3},
        {"duration_ms": -1},
        {"provider_key": ""},
        {"model_id": ""},
        {"model_id": "model with spaces"},
        {"input_sha256": "invalid"},
        {"rendered_system_sha256": "invalid"},
        {"rendered_user_sha256": "invalid"},
        {"output_sha256": "invalid"},
        {"input_json": None},
        {"provider_cost": -1, "cost_currency": "USD"},
        {"provider_cost": 1, "cost_currency": None},
        {"provider_cost": None, "cost_currency": "USD"},
        {"provider_cost": 1, "cost_currency": "usd"},
        {"prompt_checksum": "0" * 64},
    ]
    for values in invalid_updates:
        with pytest.raises(IntegrityError), db_connection.begin_nested():
            db_connection.execute(
                update(AiExecutionRun)
                .where(AiExecutionRun.id == execution.id)
                .values(**values)
            )
    with pytest.raises(DataError), db_connection.begin_nested():
        db_connection.execute(
            update(AiExecutionRun)
            .where(AiExecutionRun.id == execution.id)
            .values(model_id="x" * (AI_MODEL_IDENTIFIER_MAX_LENGTH + 1))
        )
    invalid_request_ids = [
        "",
        " ",
        "  ",
        "\t",
        "\n",
        "\r",
        " leading",
        "trailing ",
        "embedded\x1fcontrol",
        "embedded\x7fcontrol",
        "embedded\x80control",
    ]
    for request_id in invalid_request_ids:
        with (
            pytest.raises(IntegrityError) as invalid_request,
            db_connection.begin_nested(),
        ):
            db_connection.execute(
                update(AiExecutionRun)
                .where(AiExecutionRun.id == execution.id)
                .values(request_id=request_id)
            )
        assert invalid_request.value.orig.diag.constraint_name == (
            "ck_ai_execution_runs_request_id"
        )
    for request_id in ("embedded\x00control", "x" * 101):
        with pytest.raises(DataError), db_connection.begin_nested():
            db_connection.execute(
                update(AiExecutionRun)
                .where(AiExecutionRun.id == execution.id)
                .values(request_id=request_id)
            )
    for request_id in ("x", "x" * 100, str(uuid4()), "provider/request:123"):
        with db_connection.begin_nested() as savepoint:
            db_connection.execute(
                update(AiExecutionRun)
                .where(AiExecutionRun.id == execution.id)
                .values(request_id=request_id)
            )
            assert (
                db_connection.scalar(
                    select(AiExecutionRun.request_id).where(
                        AiExecutionRun.id == execution.id
                    )
                )
                == request_id
            )
            savepoint.rollback()
    with (
        pytest.raises(IntegrityError) as duplicate_request,
        db_connection.begin_nested(),
    ):
        db_connection.execute(
            update(AiExecutionRun)
            .where(AiExecutionRun.id == second.id)
            .values(request_id=execution.request_id)
        )
    assert duplicate_request.value.orig.diag.constraint_name == (
        "uq_ai_execution_runs_request_id"
    )
    with pytest.raises(IntegrityError), db_connection.begin_nested():
        db_connection.execute(
            AiPromptVersion.__table__.delete().where(AiPromptVersion.id == prompt["id"])
        )


def test_read_only_audit_retrieval_has_one_select_and_no_write_or_lock(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        execution = _coordinator(session, FakeProvider()).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    statements: list[str] = []

    def capture(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement)

    event.listen(db_connection, "before_cursor_execute", capture)
    try:
        response = client.get(f"/api/v1/ai-execution-runs/{execution.id}")
    finally:
        event.remove(db_connection, "before_cursor_execute", capture)
    assert response.status_code == 200
    relevant = [
        statement.lower()
        for statement in statements
        if "ai_execution_runs" in statement
    ]
    assert len(relevant) == 1
    assert relevant[0].lstrip().startswith("select")
    assert "for update" not in relevant[0]
    assert all(
        keyword not in " ".join(relevant)
        for keyword in ("insert ", "update ", "delete ")
    )
    assert db_connection.scalar(select(func.count()).select_from(SourceChunk)) == 0


def test_gemini_disabled_and_settings_are_secret_safe() -> None:
    provider = GeminiProvider("")
    with pytest.raises(AiProviderError, match="AI_PROVIDER_DISABLED"):
        provider.generate(
            AiProviderRequest("request", "model", "system", "user", {}, 1, 1, 0)
        )
    configured = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://localhost/test",
        gemini_api_key="  secret-value  ",
        gemini_model="models/allowed",
        ai_model_allowlist="models/allowed",
    )
    assert configured.gemini_api_key.get_secret_value() == "secret-value"
    assert "secret-value" not in repr(configured)
    assert "secret-value" not in str(configured)
    assert "secret-value" not in configured.model_dump_json()
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://localhost/test",
            gemini_model="models/blocked",
            ai_model_allowlist="models/allowed",
        )

    blank = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://localhost/test",
        gemini_api_key="",
        gemini_model="",
    )
    assert blank.gemini_api_key.get_secret_value() == ""
    assert blank.gemini_model == ""

    secret = "dummy-test-secret"
    with pytest.raises(ValueError) as raised:
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://localhost/test",
            gemini_api_key=secret,
            gemini_model=" invalid model ",
        )
    assert secret not in str(raised.value)

    class HostileSecret(str):
        def strip(self, _characters=None):
            raise LookupError("hostile-secret-detail")

    with pytest.raises(ValueError) as hostile_error:
        Settings(
            _env_file=None,
            database_url="postgresql+psycopg://localhost/test",
            gemini_api_key=HostileSecret("fake-api-key"),
        )
    assert "hostile-secret-detail" not in str(hostile_error.value)
    assert "fake-api-key" not in str(hostile_error.value)


def test_disabled_gemini_creates_failed_audit_without_secret(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        result = _coordinator(session, GeminiProvider("")).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    serialized = result.model_dump_json()
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_DISABLED"
    assert "api_key" not in serialized.lower()
    assert "authorization" not in serialized.lower()


def test_repeated_executions_are_independent_with_distinct_request_ids(
    client: TestClient, db_connection: Connection
) -> None:
    prompt = _create_prompt(client)
    request_ids = iter(["request-one", "request-two"])
    times = iter(
        [
            datetime(2026, 9, 12, 5, 0, tzinfo=UTC),
            datetime(2026, 9, 12, 5, 0, 0, 1000, tzinfo=UTC),
            datetime(2026, 9, 12, 5, 0, 1, tzinfo=UTC),
            datetime(2026, 9, 12, 5, 0, 1, 1000, tzinfo=UTC),
        ]
    )
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        provider = FakeProvider(session=session)
        coordinator = AiExecutionCoordinator(
            lambda: Session(
                bind=db_connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            ),
            provider,
            AiExecutionOptions("models/test", 1, 10, 0),
            {("test.input", 1): InputContract},
            {("test.output", 1): OutputContract},
            clock=lambda: next(times),
            request_id_factory=lambda: next(request_ids),
        )
        first = coordinator.execute(prompt["id"], {"topic": "Assam", "count": 1})
        second = coordinator.execute(prompt["id"], {"topic": "Assam", "count": 1})
    assert first.id != second.id
    assert first.request_id == "request-one"
    assert second.request_id == "request-two"
    assert len(provider.calls) == 2


def test_gemini_adapter_uses_structured_request_timeout_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class Usage:
        prompt_token_count = 2
        candidates_token_count = 3
        total_token_count = 5

    class Models:
        def generate_content(self, **kwargs):
            captured["generate"] = kwargs
            return type(
                "Response",
                (),
                {
                    "text": '{"answer":"ok","score":2}',
                    "response_id": "safe-request-id",
                    "usage_metadata": Usage(),
                    "candidates": [],
                },
            )()

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs
            self.models = Models()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            captured["closed"] = True

    monkeypatch.setattr("app.services.gemini.genai.Client", Client)
    request = AiProviderRequest(
        "request-id",
        "models/test",
        "exact system",
        "exact user",
        {"type": "object"},
        2.5,
        99,
        0,
    )
    result = GeminiProvider(" secret ").generate(request)
    assert captured["closed"] is True
    assert captured["client"]["api_key"] == "secret"
    assert captured["client"]["http_options"].timeout == 2500
    assert captured["generate"]["model"] == "models/test"
    assert captured["generate"]["contents"] == "exact user"
    config = captured["generate"]["config"]
    assert config.system_instruction == "exact system"
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema == {"type": "object"}
    assert config.max_output_tokens == 99
    assert result.provider_request_id == "safe-request-id"
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (2, 3, 5)


def test_gemini_adapter_closes_client_and_maps_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = False

    class Models:
        def generate_content(self, **_kwargs):
            raise TimeoutError

    class Client:
        models = Models()

        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            nonlocal closed
            closed = True

    monkeypatch.setattr("app.services.gemini.genai.Client", Client)
    with pytest.raises(AiProviderError, match="AI_PROVIDER_TIMEOUT"):
        GeminiProvider("secret").generate(
            AiProviderRequest("id", "model", "system", "user", {}, 1, 1, 0)
        )
    assert closed is True


def _gemini_request() -> AiProviderRequest:
    return AiProviderRequest(
        "request-id",
        "models/gemini-2.5-flash",
        "exact system",
        "exact user",
        {"type": "object", "additionalProperties": False},
        2.5,
        99,
        0,
    )


def _install_gemini_stub(
    monkeypatch: pytest.MonkeyPatch,
    *,
    response: object | None = None,
    failure: BaseException | None = None,
) -> dict[str, object]:
    state: dict[str, object] = {"calls": 0, "closed": False, "exits": 0}

    class Models:
        def generate_content(self, **kwargs):
            state["calls"] = int(state["calls"]) + 1
            state["generate"] = kwargs
            if failure is not None:
                raise failure
            return response

    class Client:
        def __init__(self, **kwargs):
            state["client"] = kwargs
            self.models = Models()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            state["exits"] = int(state["exits"]) + 1
            state["closed"] = True

    monkeypatch.setattr("app.services.gemini.genai.Client", Client)
    return state


def _assert_gemini_request_and_cleanup(
    state: dict[str, object],
    *,
    timeout_ms: int = 2500,
    model: str = "models/gemini-2.5-flash",
    system_prompt: str = "exact system",
    user_prompt: str = "exact user",
) -> None:
    assert state["calls"] == 1
    assert state["closed"] is True
    assert state["exits"] == 1
    client = state["client"]
    generated = state["generate"]
    assert isinstance(client, dict)
    assert isinstance(generated, dict)
    assert client["http_options"].timeout == timeout_ms
    assert generated["model"] == model
    assert generated["contents"] == user_prompt
    config = generated["config"]
    assert config.system_instruction == system_prompt
    assert config.response_mime_type == "application/json"
    assert config.response_json_schema["type"] == "object"
    assert config.response_json_schema["additionalProperties"] is False


@pytest.mark.parametrize(
    ("phase", "expected_code", "expected_calls", "expected_exits"),
    [
        ("construction", "AI_PROVIDER_ERROR", 0, 0),
        ("enter", "AI_PROVIDER_ERROR", 0, 0),
        ("generation", "AI_PROVIDER_ERROR", 1, 1),
        ("normalization", "AI_PROVIDER_RESPONSE_INVALID", 1, 1),
        ("exit", "AI_PROVIDER_ERROR", 1, 1),
    ],
)
@pytest.mark.parametrize("failure_type", [Exception, LookupError])
def test_gemini_arbitrary_sdk_exceptions_are_fully_bounded_and_sanitized(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    expected_code: str,
    expected_calls: int,
    expected_exits: int,
    failure_type: type[Exception],
) -> None:
    secret_detail = "dummy-test-key credential-marker hostile-upstream-body"
    state = {"calls": 0, "enters": 0, "exits": 0}

    class Response:
        text = '{"answer":"ok","score":2}'
        response_id = None
        usage_metadata = None

        @property
        def candidates(self):
            if phase == "normalization":
                raise failure_type(secret_detail)
            return []

    class Models:
        def generate_content(self, **_kwargs):
            state["calls"] += 1
            if phase == "generation":
                raise failure_type(secret_detail)
            return Response()

    class Client:
        models = Models()

        def __init__(self, **_kwargs):
            if phase == "construction":
                raise failure_type(secret_detail)

        def __enter__(self):
            state["enters"] += 1
            if phase == "enter":
                raise failure_type(secret_detail)
            return self

        def __exit__(self, *_args):
            state["exits"] += 1
            if phase == "exit":
                raise failure_type(secret_detail)

    monkeypatch.setattr("app.services.gemini.genai.Client", Client)
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert type(raised.value) is AiProviderError
    assert str(raised.value) == expected_code
    assert secret_detail not in str(raised.value)
    assert "dummy-test-key" not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    assert raised.value.__suppress_context__ is True
    assert state["calls"] == expected_calls
    assert state["enters"] == (0 if phase == "construction" else 1)
    assert state["exits"] == expected_exits


def test_gemini_does_not_swallow_base_exception_and_still_exits_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _install_gemini_stub(
        monkeypatch, failure=KeyboardInterrupt("operator interrupt")
    )
    with pytest.raises(KeyboardInterrupt, match="operator interrupt"):
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (401, "AI_PROVIDER_AUTHENTICATION"),
        (403, "AI_PROVIDER_AUTHENTICATION"),
        (429, "AI_PROVIDER_RATE_LIMITED"),
        (408, "AI_PROVIDER_TIMEOUT"),
        (504, "AI_PROVIDER_TIMEOUT"),
        (503, "AI_PROVIDER_UNAVAILABLE"),
        (400, "AI_PROVIDER_TRANSPORT"),
    ],
)
def test_gemini_sdk_api_failures_are_sanitized_closed_and_not_retried(
    monkeypatch: pytest.MonkeyPatch, status_code: int, expected: str
) -> None:
    sensitive_detail = "dummy-key upstream-body authorization-header"

    class StubApiError(Exception):
        def __init__(self, code: int) -> None:
            self.code = code
            super().__init__(sensitive_detail)

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(monkeypatch, failure=StubApiError(status_code))
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert str(raised.value) == expected
    assert sensitive_detail not in str(raised.value)
    assert "dummy-test-key" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("UNAUTHENTICATED", "AI_PROVIDER_AUTHENTICATION"),
        ("PERMISSION_DENIED", "AI_PROVIDER_AUTHENTICATION"),
        ("RESOURCE_EXHAUSTED", "AI_PROVIDER_RATE_LIMITED"),
        ("DEADLINE_EXCEEDED", "AI_PROVIDER_TIMEOUT"),
        ("UNAVAILABLE", "AI_PROVIDER_UNAVAILABLE"),
    ],
)
def test_gemini_sdk_safe_status_failures_retain_specific_mappings(
    monkeypatch: pytest.MonkeyPatch, status: str, expected: str
) -> None:
    class StubApiError(Exception):
        code = None

        def __init__(self, message: str) -> None:
            self.status = status
            super().__init__(message)

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(
        monkeypatch,
        failure=StubApiError("fake-api-key credential header upstream-body"),
    )
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("fake-api-key").generate(_gemini_request())
    assert raised.value.error_code == expected
    assert "fake-api-key" not in str(raised.value)
    assert "upstream-body" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_sdk_failure_persists_only_stable_code_without_secret(
    client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = _create_prompt(client)
    sensitive_detail = "dummy-test-key authorization-header upstream-body"

    class StubApiError(Exception):
        code = 401

        def __init__(self) -> None:
            super().__init__(sensitive_detail)

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(monkeypatch, failure=StubApiError())
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        result = _coordinator(session, GeminiProvider("dummy-test-key")).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    serialized = result.model_dump_json()
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_AUTHENTICATION"
    assert sensitive_detail not in serialized
    assert "dummy-test-key" not in serialized
    assert "authorization-header" not in serialized
    assert "upstream-body" not in serialized
    stored_error = db_connection.scalar(
        select(AiExecutionRun.error_code).where(AiExecutionRun.id == result.id)
    )
    assert stored_error == "AI_PROVIDER_AUTHENTICATION"
    _assert_gemini_request_and_cleanup(
        state,
        timeout_ms=7500,
        model="models/test-model",
        system_prompt="Answer about Assam.",
        user_prompt="Return 1 facts for Assam.",
    )


def test_arbitrary_gemini_failure_persists_one_sanitized_failed_audit_and_commit(
    client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = _create_prompt(client)
    secret_detail = "dummy-test-key credential-marker arbitrary-sdk-failure"
    state = _install_gemini_stub(monkeypatch, failure=LookupError(secret_detail))
    session_factory = TrackingSessionFactory(db_connection)
    result = _coordinator(session_factory, GeminiProvider("dummy-test-key")).execute(
        prompt["id"], {"topic": "Assam", "count": 1}
    )
    serialized = result.model_dump_json()
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_ERROR"
    assert secret_detail not in serialized
    assert "dummy-test-key" not in serialized
    assert "credential-marker" not in serialized
    assert session_factory.commit_count == 1
    assert session_factory.rollback_count == 0
    assert session_factory.open_sessions == 0
    assert (
        db_connection.scalar(
            select(func.count())
            .select_from(AiExecutionRun)
            .where(
                AiExecutionRun.id == result.id,
                AiExecutionRun.status == "FAILED",
                AiExecutionRun.error_code == "AI_PROVIDER_ERROR",
            )
        )
        == 1
    )
    _assert_gemini_request_and_cleanup(
        state,
        timeout_ms=7500,
        model="models/test-model",
        system_prompt="Answer about Assam.",
        user_prompt="Return 1 facts for Assam.",
    )


def test_hostile_gemini_api_error_persists_one_sanitized_failed_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if not (engine.url.database or "").endswith("_test"):
        pytest.fail("AI execution tests require a dedicated *_test database")
    payload = {
        **_prompt_payload(),
        "prompt_key": f"test.hostile-api-audit.{uuid4().hex}",
    }
    with Session(bind=engine, expire_on_commit=False) as seed_session:
        prompt = AiPromptService(seed_session).create(
            AiPromptVersionCreate.model_validate(payload)
        )

    hostile_detail = "hostile-lookup-detail"
    fake_key = "fake-api-key-for-test"
    credential = "credential-test-marker"
    header = "authorization-header-test-marker"
    body = "upstream-body-test-marker"
    checked_out = 0
    state = {"calls": 0, "enters": 0, "exits": 0}
    sql_after_commit: list[str] = []
    session_factory = TrackingSessionFactory(engine, close_resets_only=False)

    class HostileInteger(int):
        def __hash__(self):
            raise LookupError(hostile_detail)

        def __eq__(self, _other):
            raise LookupError(hostile_detail)

        def __ge__(self, _other):
            raise LookupError(hostile_detail)

    class StubApiError(Exception):
        code = HostileInteger(401)
        status = None

    class Models:
        def generate_content(self, **_kwargs):
            state["calls"] += 1
            assert checked_out == 0
            assert session_factory.open_sessions == 0
            raise StubApiError(
                f"{hostile_detail} {fake_key} {credential} {header} {body}"
            )

    class Client:
        models = Models()

        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            state["enters"] += 1
            return self

        def __exit__(self, *_args):
            state["exits"] += 1

    def checkout(_dbapi_connection, _connection_record, _connection_proxy) -> None:
        nonlocal checked_out
        checked_out += 1

    def checkin(_dbapi_connection, _connection_record) -> None:
        nonlocal checked_out
        checked_out -= 1

    def capture(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        if session_factory.commit_count:
            sql_after_commit.append(statement)

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    monkeypatch.setattr("app.services.gemini.genai.Client", Client)
    event.listen(engine, "checkout", checkout)
    event.listen(engine, "checkin", checkin)
    event.listen(engine, "before_cursor_execute", capture)
    execution_id: int | None = None
    try:
        result = _coordinator(
            session_factory, GeminiProvider(fake_key)
        ).execute(prompt.id, {"topic": "Assam", "count": 1})
        execution_id = result.id
        assert checked_out == 0
        assert sql_after_commit == []
    finally:
        event.remove(engine, "before_cursor_execute", capture)
        event.remove(engine, "checkout", checkout)
        event.remove(engine, "checkin", checkin)

    try:
        serialized = result.model_dump_json()
        assert state == {"calls": 1, "enters": 1, "exits": 1}
        assert session_factory.commit_count == 1
        assert session_factory.rollback_count == 0
        assert session_factory.open_sessions == 0
        assert result.status == "FAILED"
        assert result.error_code == "AI_PROVIDER_TRANSPORT"
        assert result.output_json is None
        assert result.output_sha256 is None
        assert result.provider_request_id is None
        assert result.finish_reason is None
        assert result.safety_metadata is None
        assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
            None,
            None,
            None,
        )
        for secret in (hostile_detail, fake_key, credential, header, body):
            assert secret not in serialized
        with Session(bind=engine) as verify_session:
            stored = verify_session.scalars(
                select(AiExecutionRun).where(AiExecutionRun.id == result.id)
            ).all()
            assert len(stored) == 1
            assert stored[0].status == "FAILED"
            assert stored[0].error_code == "AI_PROVIDER_TRANSPORT"
            assert stored[0].output_json is None
            assert stored[0].output_sha256 is None
    finally:
        with Session(bind=engine) as cleanup_session:
            if execution_id is not None:
                cleanup_session.execute(
                    delete(AiExecutionRun).where(AiExecutionRun.id == execution_id)
                )
            cleanup_session.execute(
                delete(AiPromptVersion).where(AiPromptVersion.id == prompt.id)
            )
            cleanup_session.commit()


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (TimeoutError("sensitive timeout detail"), "AI_PROVIDER_TIMEOUT"),
        (OSError("sensitive socket detail"), "AI_PROVIDER_TRANSPORT"),
        (RuntimeError("sensitive runtime detail"), "AI_PROVIDER_TRANSPORT"),
        (ValueError("sensitive response detail"), "AI_PROVIDER_TRANSPORT"),
    ],
)
def test_gemini_transport_failures_close_once_without_retry_or_detail(
    monkeypatch: pytest.MonkeyPatch, failure: BaseException, expected: str
) -> None:
    state = _install_gemini_stub(monkeypatch, failure=failure)
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert str(raised.value) == expected
    assert "sensitive" not in str(raised.value)
    assert "dummy-test-key" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_api_error_with_inaccessible_code_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StubApiError(Exception):
        @property
        def code(self):
            raise RuntimeError("sensitive code getter")

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(monkeypatch, failure=StubApiError("secret body"))
    with pytest.raises(AiProviderError, match="^AI_PROVIDER_TRANSPORT$") as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "secret" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("malformed_code", [None, True, "401", object()])
def test_gemini_api_error_with_malformed_code_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, malformed_code: object
) -> None:
    class StubApiError(Exception):
        code = malformed_code

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(monkeypatch, failure=StubApiError("secret body"))
    with pytest.raises(AiProviderError, match="^AI_PROVIDER_TRANSPORT$") as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "secret" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    "hostile_case",
    [
        "code_property",
        "status_property",
        "code_hash",
        "code_eq",
        "code_comparison",
        "code_bool",
        "status_hash",
        "status_eq",
        "status_value_conversion",
        "malformed_code_and_status",
    ],
)
def test_gemini_hostile_api_error_metadata_is_total_sanitized_and_not_retried(
    monkeypatch: pytest.MonkeyPatch, hostile_case: str
) -> None:
    hostile_detail = "lookup-hostile-detail"
    fake_key = "fake-api-key-for-test"
    credential = "credential-test-marker"
    header = "authorization-header-test-marker"
    body = "upstream-body-test-marker"

    class HostileOperation(LookupError):
        pass

    class HostileIntHash(int):
        def __hash__(self):
            raise HostileOperation(hostile_detail)

    class HostileIntEq(int):
        def __eq__(self, _other):
            raise HostileOperation(hostile_detail)

    class HostileIntComparison(int):
        def __ge__(self, _other):
            raise HostileOperation(hostile_detail)

        def __le__(self, _other):
            raise HostileOperation(hostile_detail)

    class HostileStrHash(str):
        def __hash__(self):
            raise HostileOperation(hostile_detail)

    class HostileStrEq(str):
        def __eq__(self, _other):
            raise HostileOperation(hostile_detail)

    class HostileStatusValue:
        @property
        def value(self):
            raise HostileOperation(hostile_detail)

        def __str__(self):
            raise HostileOperation(hostile_detail)

    code: object = None
    status: object = None
    if hostile_case == "code_hash":
        code = HostileIntHash(401)
    elif hostile_case == "code_eq":
        code = HostileIntEq(401)
    elif hostile_case == "code_comparison":
        code = HostileIntComparison(503)
    elif hostile_case == "code_bool":
        code = True
    elif hostile_case == "status_hash":
        status = HostileStrHash("UNAUTHENTICATED")
    elif hostile_case == "status_eq":
        status = HostileStrEq("UNAVAILABLE")
    elif hostile_case == "status_value_conversion":
        status = HostileStatusValue()
    elif hostile_case == "malformed_code_and_status":
        code = object()
        status = object()

    class StubApiError(Exception):
        @property
        def code(self):
            if hostile_case == "code_property":
                raise HostileOperation(hostile_detail)
            return code

        @property
        def status(self):
            if hostile_case == "status_property":
                raise HostileOperation(hostile_detail)
            return status

    message = f"{fake_key} {credential} {header} {body} {hostile_detail}"
    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(monkeypatch, failure=StubApiError(message))

    with pytest.raises(AiProviderError) as raised:
        GeminiProvider(fake_key).generate(_gemini_request())

    assert type(raised.value) is AiProviderError
    assert raised.value.error_code == "AI_PROVIDER_TRANSPORT"
    assert str(raised.value) == "AI_PROVIDER_TRANSPORT"
    assert raised.value.__suppress_context__ is True
    for secret in (hostile_detail, fake_key, credential, header, body):
        assert secret not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_hostile_integer_like_code_reviewer_regression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_detail = "reviewer-hostile-lookup-detail"

    class HostileInteger(int):
        def __hash__(self):
            raise LookupError(hostile_detail)

        def __eq__(self, _other):
            raise LookupError(hostile_detail)

        def __ge__(self, _other):
            raise LookupError(hostile_detail)

    class StubApiError(Exception):
        code = HostileInteger(401)
        status = None

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    state = _install_gemini_stub(
        monkeypatch, failure=StubApiError("unsafe reviewer upstream body")
    )

    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("fake-api-key-for-test").generate(_gemini_request())

    normalized_code = raised.value.error_code
    hostile_detail_present = hostile_detail in str(raised.value)
    assert normalized_code == "AI_PROVIDER_TRANSPORT"
    assert hostile_detail_present is False
    assert not isinstance(raised.value, LookupError)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_api_error_mapping_failure_is_caught_by_outer_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hostile_detail = "mapping-helper-hostile-detail"

    class StubApiError(Exception):
        code = 401

    def fail_mapping(_error: object) -> str:
        raise LookupError(hostile_detail)

    monkeypatch.setattr("app.services.gemini.errors.APIError", StubApiError)
    monkeypatch.setattr("app.services.gemini._map_api_error", fail_mapping)
    state = _install_gemini_stub(
        monkeypatch, failure=StubApiError("fake-api-key credential header body")
    )

    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("fake-api-key").generate(_gemini_request())

    assert raised.value.error_code == "AI_PROVIDER_ERROR"
    assert hostile_detail not in str(raised.value)
    assert raised.value.__suppress_context__ is True
    _assert_gemini_request_and_cleanup(state)


def test_map_api_error_is_total_for_hostile_ordinary_metadata() -> None:
    class HostileMetadata:
        @property
        def code(self):
            raise LookupError("HOSTILE_DETAIL")

        @property
        def status(self):
            raise RuntimeError("HOSTILE_DETAIL")

    normalized_code = _map_api_error(HostileMetadata())
    hostile_detail_present = "HOSTILE_DETAIL" in normalized_code
    assert normalized_code == "AI_PROVIDER_TRANSPORT"
    assert hostile_detail_present is False


@pytest.mark.parametrize("candidates", [object(), {}, "candidate", iter(())])
def test_gemini_rejects_non_sequence_candidates_without_iteration(
    monkeypatch: pytest.MonkeyPatch, candidates: object
) -> None:
    response = type("Response", (), {"candidates": candidates})()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"):
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    _assert_gemini_request_and_cleanup(state)


def test_gemini_does_not_iterate_or_slice_hostile_candidate_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HostileCandidates:
        def __iter__(self):
            raise RuntimeError("sensitive candidate iteration")

        def __getitem__(self, _index):
            raise RuntimeError("sensitive candidate slicing")

    response = type("Response", (), {"candidates": HostileCandidates()})()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("base", [list, tuple])
def test_gemini_accepted_candidate_collection_hostile_index_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, base: type
) -> None:
    secret_detail = "dummy-test-key credential-marker candidate-index"
    iter_calls = 0

    class HostileCandidates(base):
        def __getitem__(self, _index):
            raise LookupError(secret_detail)

        def __iter__(self):
            nonlocal iter_calls
            iter_calls += 1
            raise AssertionError("candidate normalization must use bounded indexing")

    response = type("Response", (), {"candidates": HostileCandidates([object()])})()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert secret_detail not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    assert iter_calls == 0
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    "attribute", ["candidates", "text", "usage_metadata", "response_id"]
)
def test_gemini_inaccessible_response_metadata_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    class Response:
        candidates = ()
        text = '{"answer":"ok","score":2}'
        usage_metadata = None
        response_id = None

    def explode(_self):
        raise RuntimeError("sensitive response metadata")

    setattr(Response, attribute, property(explode))
    state = _install_gemini_stub(monkeypatch, response=Response())
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_metadata_failure_persists_only_sanitized_terminal_code(
    client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = _create_prompt(client)

    class Response:
        @property
        def candidates(self):
            raise RuntimeError("dummy-test-key upstream-body authorization-header")

    state = _install_gemini_stub(monkeypatch, response=Response())
    result = _coordinator(
        lambda: Session(
            bind=db_connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ),
        GeminiProvider("dummy-test-key"),
    ).execute(prompt["id"], {"topic": "Assam", "count": 1})
    serialized = result.model_dump_json()
    assert result.status == "FAILED"
    assert result.error_code == "AI_PROVIDER_RESPONSE_INVALID"
    assert "dummy-test-key" not in serialized
    assert "upstream-body" not in serialized
    assert "authorization-header" not in serialized
    assert (
        db_connection.scalar(
            select(AiExecutionRun.error_code).where(AiExecutionRun.id == result.id)
        )
        == "AI_PROVIDER_RESPONSE_INVALID"
    )
    _assert_gemini_request_and_cleanup(
        state,
        timeout_ms=7500,
        model="models/test-model",
        system_prompt="Answer about Assam.",
        user_prompt="Return 1 facts for Assam.",
    )


@pytest.mark.parametrize("attribute", ["finish_reason", "safety_ratings"])
def test_gemini_inaccessible_candidate_metadata_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    class Candidate:
        finish_reason = None
        safety_ratings = ()

    def explode(_self):
        raise RuntimeError("sensitive candidate metadata")

    setattr(Candidate, attribute, property(explode))
    response = type(
        "Response",
        (),
        {
            "candidates": [Candidate()],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("attribute", ["category", "probability", "blocked"])
def test_gemini_inaccessible_rating_metadata_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    class Rating:
        category = "HARM_CATEGORY_TEST"
        probability = "LOW"
        blocked = False

    def explode(_self):
        raise RuntimeError("sensitive rating metadata")

    setattr(Rating, attribute, property(explode))
    candidate = type(
        "Candidate", (), {"finish_reason": None, "safety_ratings": [Rating()]}
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_safety_metadata_is_bounded_and_never_stringifies_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnsafeValue:
        def __str__(self) -> str:
            raise AssertionError("must not stringify arbitrary provider objects")

    rating = type(
        "Rating",
        (),
        {"category": UnsafeValue(), "probability": UnsafeValue(), "blocked": "yes"},
    )()
    candidate = type(
        "Candidate",
        (),
        {"finish_reason": UnsafeValue(), "safety_ratings": [rating] * 25},
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": UnsafeValue(),
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    result = GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert result.provider_request_id is None
    assert result.finish_reason is None
    assert result.safety_metadata is not None
    assert len(result.safety_metadata["ratings"]) == 20
    assert result.safety_metadata["ratings"][0] == {
        "category": None,
        "probability": None,
        "blocked": None,
    }
    _assert_gemini_request_and_cleanup(state)


def test_gemini_inaccessible_or_non_sequence_safety_ratings_are_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = type(
        "Candidate", (), {"finish_reason": None, "safety_ratings": iter(())}
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"):
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    _assert_gemini_request_and_cleanup(state)


def test_gemini_does_not_iterate_or_slice_hostile_safety_collection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HostileRatings:
        def __iter__(self):
            raise RuntimeError("sensitive rating iteration")

        def __getitem__(self, _index):
            raise RuntimeError("sensitive rating slicing")

    candidate = type(
        "Candidate", (), {"finish_reason": None, "safety_ratings": HostileRatings()}
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_accepted_safety_collection_hostile_slice_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_detail = "dummy-test-key credential-marker rating-slice"

    class HostileRatings(list):
        def __getitem__(self, index):
            if isinstance(index, slice):
                raise LookupError(secret_detail)  # noqa: TRY004 -- hostile SDK behavior
            return super().__getitem__(index)

    candidate = type(
        "Candidate",
        (),
        {"finish_reason": None, "safety_ratings": HostileRatings([object()])},
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert secret_detail not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_accepted_safety_collection_hostile_iteration_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_detail = "dummy-test-key credential-marker rating-iteration"

    class HostileSlice(list):
        def __iter__(self):
            raise LookupError(secret_detail)

    class HostileRatings(list):
        def __getitem__(self, index):
            if isinstance(index, slice):
                return HostileSlice(super().__getitem__(index))
            return super().__getitem__(index)

    candidate = type(
        "Candidate",
        (),
        {"finish_reason": None, "safety_ratings": HostileRatings([object()])},
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert secret_detail not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("field", ["finish_reason", "category", "probability"])
def test_gemini_hostile_enum_conversion_is_sanitized(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    secret_detail = f"dummy-test-key credential-marker {field}-conversion"

    class HostileEnum(Enum):
        VALUE = "safe"

        @property
        def value(self):
            raise LookupError(secret_detail)

    rating = type(
        "Rating",
        (),
        {
            "category": HostileEnum.VALUE if field == "category" else "CATEGORY",
            "probability": HostileEnum.VALUE if field == "probability" else "LOW",
            "blocked": False,
        },
    )()
    candidate = type(
        "Candidate",
        (),
        {
            "finish_reason": HostileEnum.VALUE if field == "finish_reason" else None,
            "safety_ratings": [rating],
        },
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert secret_detail not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_hostile_safety_element_property_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_detail = "dummy-test-key credential-marker hostile-element"

    class Rating:
        @property
        def category(self):
            raise LookupError(secret_detail)

        probability = "LOW"
        blocked = False

    candidate = type(
        "Candidate", (), {"finish_reason": None, "safety_ratings": [Rating()]}
    )()
    response = type(
        "Response",
        (),
        {
            "candidates": [candidate],
            "text": '{"answer":"ok","score":2}',
            "usage_metadata": None,
            "response_id": None,
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert secret_detail not in str(raised.value)
    assert "credential-marker" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_safety_block_closes_client_and_returns_only_stable_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = type(
        "Candidate",
        (),
        {"finish_reason": "SAFETY", "safety_ratings": []},
    )()
    response = type(
        "Response",
        (),
        {"text": "upstream body", "candidates": [candidate]},
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert str(raised.value) == "AI_PROVIDER_SAFETY_BLOCKED"
    assert "upstream body" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("text", [None, "", "   "])
def test_gemini_missing_or_empty_text_is_sanitized_and_closed(
    monkeypatch: pytest.MonkeyPatch, text: str | None
) -> None:
    response = type("Response", (), {"text": text, "candidates": []})()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"):
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    _assert_gemini_request_and_cleanup(state)


def test_gemini_inaccessible_text_is_sanitized_and_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Response:
        candidates = ()

        @property
        def text(self):
            raise RuntimeError("sensitive response body")

    state = _install_gemini_stub(monkeypatch, response=Response())
    with pytest.raises(AiProviderError) as raised:
        GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert str(raised.value) == "AI_PROVIDER_RESPONSE_INVALID"
    assert "sensitive" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


def test_gemini_string_subclass_response_is_rejected_without_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HostileText(str):
        def strip(self, _characters=None):
            raise LookupError("fake-api-key hostile-response-text")

    response = type(
        "Response",
        (),
        {"text": HostileText('{"answer":"ok","score":2}'), "candidates": []},
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with pytest.raises(
        AiProviderError, match="^AI_PROVIDER_RESPONSE_INVALID$"
    ) as raised:
        GeminiProvider("fake-api-key").generate(_gemini_request())
    assert "fake-api-key" not in str(raised.value)
    assert "hostile-response-text" not in str(raised.value)
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize("usage", [None, object(), MalformedUsage()])
def test_gemini_missing_or_malformed_usage_is_optional_and_safe(
    monkeypatch: pytest.MonkeyPatch, usage: object | None
) -> None:
    response = type(
        "Response",
        (),
        {
            "text": '{"answer":"ok","score":2}',
            "response_id": "request\nidentifier",
            "usage_metadata": usage,
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    result = GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    assert result.provider_request_id is None
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    "usage",
    [
        type(
            "HugeUsage",
            (),
            {
                "prompt_token_count": 2_147_483_648,
                "candidates_token_count": 1,
                "total_token_count": 2_147_483_649,
            },
        )(),
        type(
            "BooleanUsage",
            (),
            {
                "prompt_token_count": True,
                "candidates_token_count": 1,
                "total_token_count": 2,
            },
        )(),
        type(
            "FloatUsage",
            (),
            {
                "prompt_token_count": 1.0,
                "candidates_token_count": 1,
                "total_token_count": 2,
            },
        )(),
    ],
)
def test_gemini_unsafe_usage_values_are_omitted(
    monkeypatch: pytest.MonkeyPatch, usage: object
) -> None:
    response = type(
        "Response",
        (),
        {
            "text": '{"answer":"ok","score":2}',
            "response_id": None,
            "usage_metadata": usage,
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    result = GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    _assert_gemini_request_and_cleanup(state)


def test_gemini_integer_subclass_usage_is_omitted_without_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class HostileToken(int):
        def __eq__(self, _other):
            raise LookupError("fake-api-key hostile-token")

        def __ge__(self, _other):
            raise LookupError("fake-api-key hostile-token")

    usage = type(
        "Usage",
        (),
        {
            "prompt_token_count": HostileToken(1),
            "candidates_token_count": 1,
            "total_token_count": 2,
        },
    )()
    response = type(
        "Response",
        (),
        {
            "text": '{"answer":"ok","score":2}',
            "response_id": None,
            "usage_metadata": usage,
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    result = GeminiProvider("fake-api-key").generate(_gemini_request())
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    _assert_gemini_request_and_cleanup(state)


@pytest.mark.parametrize(
    "attribute", ["prompt_token_count", "candidates_token_count", "total_token_count"]
)
def test_gemini_inaccessible_usage_fields_are_omitted(
    monkeypatch: pytest.MonkeyPatch, attribute: str
) -> None:
    class Usage:
        prompt_token_count = 1
        candidates_token_count = 1
        total_token_count = 2

    def explode(_self):
        raise RuntimeError("sensitive usage metadata")

    setattr(Usage, attribute, property(explode))
    response = type(
        "Response",
        (),
        {
            "text": '{"answer":"ok","score":2}',
            "response_id": None,
            "usage_metadata": Usage(),
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    result = GeminiProvider("dummy-test-key").generate(_gemini_request())
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    _assert_gemini_request_and_cleanup(state)


def test_gemini_malformed_usage_cannot_persist_inconsistent_tokens(
    client: TestClient, db_connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = _create_prompt(client)
    usage = type(
        "Usage",
        (),
        {
            "prompt_token_count": 2,
            "candidates_token_count": 3,
            "total_token_count": 99,
        },
    )()
    response = type(
        "Response",
        (),
        {
            "text": '{"answer":"ok","score":2}',
            "response_id": None,
            "usage_metadata": usage,
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        result = _coordinator(session, GeminiProvider("dummy-test-key")).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    assert result.status == "SUCCEEDED"
    assert result.error_code is None
    assert (result.input_tokens, result.output_tokens, result.total_tokens) == (
        None,
        None,
        None,
    )
    _assert_gemini_request_and_cleanup(
        state,
        timeout_ms=7500,
        model="models/test-model",
        system_prompt="Answer about Assam.",
        user_prompt="Return 1 facts for Assam.",
    )


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("not-json", "AI_OUTPUT_INVALID_JSON"),
        ('{"answer":"ok"}', "AI_OUTPUT_SCHEMA_INVALID"),
    ],
)
def test_gemini_structured_output_is_coordinator_validated(
    client: TestClient,
    db_connection: Connection,
    monkeypatch: pytest.MonkeyPatch,
    output: str,
    expected: str,
) -> None:
    prompt = _create_prompt(client)
    response = type(
        "Response",
        (),
        {
            "text": output,
            "response_id": None,
            "usage_metadata": None,
            "candidates": [],
        },
    )()
    state = _install_gemini_stub(monkeypatch, response=response)
    with Session(
        bind=db_connection, join_transaction_mode="create_savepoint"
    ) as session:
        result = _coordinator(session, GeminiProvider("dummy-test-key")).execute(
            prompt["id"], {"topic": "Assam", "count": 1}
        )
    assert result.status == "FAILED"
    assert result.error_code == expected
    assert result.output_json is None
    _assert_gemini_request_and_cleanup(
        state,
        timeout_ms=7500,
        model="models/test-model",
        system_prompt="Answer about Assam.",
        user_prompt="Return 1 facts for Assam.",
    )
