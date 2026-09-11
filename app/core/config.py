from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Assam Exam AI"
    app_version: str = "0.1.0"
    environment: str = "development"
    debug: bool = True

    database_url: str

    official_discovery_allowed_hosts: str = ""
    official_discovery_connect_timeout_seconds: float = 5.0
    official_discovery_read_timeout_seconds: float = 10.0
    official_discovery_robots_max_bytes: int = 262_144
    official_discovery_sitemap_max_bytes: int = 1_048_576
    official_discovery_sitemap_document_limit: int = 20
    official_discovery_inspected_url_limit: int = 1_000
    official_discovery_candidate_limit: int = 50
    official_discovery_redirect_limit: int = 3
    official_discovery_user_agent: str = "AssamExamAI-OfficialDiscovery/1.0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
