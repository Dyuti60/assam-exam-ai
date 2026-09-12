import ipaddress
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AI_REQUEST_TIMEOUT_MAX_SECONDS = 120.0
AI_MAX_OUTPUT_TOKENS_LIMIT = 8_192
AI_TEMPERATURE_MIN = 0.0
AI_TEMPERATURE_MAX = 2.0
AI_MODEL_IDENTIFIER_MAX_LENGTH = 128
AI_MODEL_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
AI_NUMBER_PATTERN = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
)


def validate_ai_request_timeout(value: object) -> float:
    number = _finite_ai_number(value, "AI request timeout")
    if not 0 < number <= AI_REQUEST_TIMEOUT_MAX_SECONDS:
        raise ValueError("AI request timeout is invalid")
    return float(number)


def validate_ai_max_output_tokens(value: object) -> int:
    number = _finite_ai_number(value, "AI maximum output tokens")
    if (
        number != number.to_integral_value()
        or not 0 < number <= AI_MAX_OUTPUT_TOKENS_LIMIT
    ):
        raise ValueError("AI maximum output tokens is invalid")
    return int(number)


def validate_ai_temperature(value: object) -> float:
    number = _finite_ai_number(value, "AI temperature")
    if not AI_TEMPERATURE_MIN <= number <= AI_TEMPERATURE_MAX:
        raise ValueError("AI temperature is invalid")
    return float(number)


def _finite_ai_number(value: object, label: str) -> Decimal:
    if type(value) not in (int, float, Decimal, str):
        raise ValueError(f"{label} is invalid")
    if type(value) is str and (
        value != value.strip() or AI_NUMBER_PATTERN.fullmatch(value) is None
    ):
        raise ValueError(f"{label} is invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label} is invalid") from None
    if not number.is_finite() or (
        isinstance(value, float) and not math.isfinite(value)
    ):
        raise ValueError(f"{label} is invalid")
    return number


def _valid_official_hostname(hostname: str) -> bool:
    if len(hostname) > 253 or "." not in hostname:
        return False
    labels = hostname.split(".")
    return all(
        label
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(character.isalnum() or character == "-" for character in label)
        for label in labels
    )


class Settings(BaseSettings):
    app_name: str = "Assam Exam AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str

    official_discovery_allowed_hosts: str = ""
    official_discovery_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    official_discovery_read_timeout_seconds: float = Field(default=10.0, gt=0)
    official_discovery_robots_max_bytes: int = Field(default=262_144, gt=0)
    official_discovery_sitemap_max_bytes: int = Field(default=1_048_576, gt=0)
    official_discovery_sitemap_document_limit: int = Field(default=20, gt=0)
    official_discovery_inspected_url_limit: int = Field(default=1_000, gt=0)
    official_discovery_candidate_limit: int = Field(default=50, gt=0)
    official_discovery_redirect_limit: int = Field(default=3, ge=0)
    official_discovery_user_agent: str = "AssamExamAI-OfficialDiscovery/1.0"
    source_snapshot_max_bytes: int = Field(default=5_242_880, gt=0)
    source_fetch_allowed_hosts: str = ""
    source_fetch_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    source_fetch_read_timeout_seconds: float = Field(default=10.0, gt=0)
    source_fetch_robots_max_bytes: int = Field(default=262_144, gt=0)
    source_fetch_response_max_bytes: int = Field(default=5_242_880, gt=0)
    source_fetch_redirect_limit: int = Field(default=3, ge=0)
    source_fetch_user_agent: str = "AssamExamAI-SourceFetch/1.0"
    source_extraction_max_input_bytes: int = Field(default=5_242_880, gt=0)
    source_extraction_max_characters: int = Field(default=2_000_000, gt=0)
    source_extraction_max_chunks: int = Field(default=5_000, gt=0)
    ai_provider: str = "gemini"
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = ""
    ai_request_timeout_seconds: float = Field(
        default=30.0, gt=0, le=AI_REQUEST_TIMEOUT_MAX_SECONDS
    )
    ai_max_output_tokens: int = Field(
        default=2_048, gt=0, le=AI_MAX_OUTPUT_TOKENS_LIMIT
    )
    ai_temperature: float = Field(
        default=0.0, ge=AI_TEMPERATURE_MIN, le=AI_TEMPERATURE_MAX
    )
    ai_model_allowlist: str = ""

    @field_validator("official_discovery_allowed_hosts")
    @classmethod
    def validate_official_discovery_allowed_hosts(cls, value: str) -> str:
        return _validate_hostname_allowlist(value, "official discovery")

    @field_validator("source_fetch_allowed_hosts")
    @classmethod
    def validate_source_fetch_allowed_hosts(cls, value: str) -> str:
        return _validate_hostname_allowlist(value, "source fetch")

    @field_validator("official_discovery_user_agent", "source_fetch_user_agent")
    @classmethod
    def validate_user_agent(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 200
            or any(
                ord(character) < 32 or 127 <= ord(character) <= 159
                for character in normalized
            )
        ):
            raise ValueError("user agent is invalid")
        return normalized

    @field_validator("ai_provider")
    @classmethod
    def validate_ai_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized != "gemini":
            raise ValueError("AI provider must be gemini")
        return normalized

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def normalize_gemini_api_key(cls, value: object) -> object:
        if type(value) is str:
            return value.strip()
        if isinstance(value, str):
            raise ValueError("Gemini API key is invalid")  # noqa: TRY004
        return value

    @field_validator("gemini_model")
    @classmethod
    def validate_gemini_model(cls, value: str) -> str:
        return validate_ai_model_identifier(value, allow_blank=True)

    @field_validator("ai_request_timeout_seconds", mode="before")
    @classmethod
    def validate_ai_request_timeout_seconds(cls, value: object) -> float:
        return validate_ai_request_timeout(value)

    @field_validator("ai_max_output_tokens", mode="before")
    @classmethod
    def validate_ai_output_tokens(cls, value: object) -> int:
        return validate_ai_max_output_tokens(value)

    @field_validator("ai_temperature", mode="before")
    @classmethod
    def validate_ai_temperature_value(cls, value: object) -> float:
        return validate_ai_temperature(value)

    @field_validator("ai_model_allowlist")
    @classmethod
    def validate_ai_model_allowlist(cls, value: str) -> str:
        if not value.strip():
            return ""
        entries = value.split(",")
        if any(not entry.strip() for entry in entries):
            raise ValueError("AI model allowlist contains an empty entry")
        models = [
            validate_ai_model_identifier(entry, allow_blank=False) for entry in entries
        ]
        return ",".join(dict.fromkeys(models))

    @model_validator(mode="after")
    def validate_source_fetch_limits(self) -> Self:
        if self.source_fetch_response_max_bytes > self.source_snapshot_max_bytes:
            raise ValueError(
                "source fetch response limit cannot exceed source snapshot limit"
            )
        if self.source_extraction_max_input_bytes > self.source_snapshot_max_bytes:
            raise ValueError(
                "source extraction input limit cannot exceed source snapshot limit"
            )
        allowed_models = set(filter(None, self.ai_model_allowlist.split(",")))
        if (
            self.gemini_model
            and allowed_models
            and self.gemini_model not in allowed_models
        ):
            raise ValueError("configured Gemini model is not in AI model allowlist")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )


def _validate_hostname_allowlist(value: str, label: str) -> str:
    if not value.strip():
        return ""
    raw_hosts = value.split(",")
    if any(not host.strip() for host in raw_hosts):
        raise ValueError(f"{label} allowlist contains an empty entry")
    hosts = [host.strip().rstrip(".").lower() for host in raw_hosts]
    for host in hosts:
        if any(character.isspace() for character in host):
            raise ValueError(f"{label} allowlist entries cannot contain whitespace")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError(f"{label} allowlist entries must be hostnames")
        if host == "localhost" or not _valid_official_hostname(host):
            raise ValueError(f"{label} allowlist contains an invalid hostname")
    return ",".join(dict.fromkeys(hosts))


def validate_ai_model_identifier(value: str, *, allow_blank: bool) -> str:
    if type(value) is not str:
        raise ValueError("AI model identifier is invalid")
    if not value and allow_blank:
        return ""
    if (
        not value
        or value != value.strip()
        or len(value) > AI_MODEL_IDENTIFIER_MAX_LENGTH
        or AI_MODEL_IDENTIFIER_PATTERN.fullmatch(value) is None
    ):
        raise ValueError("AI model identifier is invalid")
    return value


settings = Settings()
