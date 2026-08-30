from app.core.config import settings


def test_settings() -> None:
    assert settings.app_name == "Assam Exam AI"
    assert settings.app_version == "0.1.0"
    assert settings.environment == "development"
    assert settings.debug is True