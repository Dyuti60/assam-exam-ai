import ipaddress

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    @field_validator("official_discovery_allowed_hosts")
    @classmethod
    def validate_official_discovery_allowed_hosts(cls, value: str) -> str:
        if not value.strip():
            return ""
        raw_hosts = value.split(",")
        if any(not host.strip() for host in raw_hosts):
            raise ValueError("official discovery allowlist contains an empty entry")
        hosts = [host.strip().rstrip(".").lower() for host in raw_hosts]
        for host in hosts:
            if any(character.isspace() for character in host):
                raise ValueError(
                    "official discovery allowlist entries cannot contain whitespace"
                )
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("official discovery allowlist entries must be hostnames")
            if host == "localhost" or not _valid_official_hostname(host):
                raise ValueError("official discovery allowlist contains an invalid hostname")
        return ",".join(dict.fromkeys(hosts))

    @field_validator("official_discovery_user_agent")
    @classmethod
    def validate_official_discovery_user_agent(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 200
            or any(
                ord(character) < 32 or 127 <= ord(character) <= 159
                for character in normalized
            )
        ):
            raise ValueError("official discovery user agent is invalid")
        return normalized

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
