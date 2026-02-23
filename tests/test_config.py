import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    base = {
        "anthropic_api_key": "test-anthropic",
        "database_url": "sqlite:///./test.db",
        "webhook_secret": "test-webhook-secret",
        "admin_api_key": "test-admin-secret",
        "allowed_origins_raw": "http://localhost:3000",
        "extraction_model": "claude-test",
        "validation_model": "claude-test",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    }
    base.update(overrides)
    return Settings(**base)


def test_validate_required_raises_for_missing_env() -> None:
    settings = _settings(database_url="")
    with pytest.raises(ValueError):
        settings.validate_required()


def test_validate_required_passes_when_admin_api_key_missing() -> None:
    settings = _settings(admin_api_key="")
    settings.validate_required()


def test_validate_required_passes_with_all_required_values() -> None:
    settings = _settings()
    settings.validate_required()


def test_validate_required_rejects_default_db_credentials_pattern() -> None:
    settings = _settings(
        database_url="postgresql+psycopg2://postgres:postgres@db:5432/contracts",
        environment="production",
    )
    with pytest.raises(ValueError):
        settings.validate_required()


def test_validate_required_rejects_same_admin_and_webhook_secret() -> None:
    settings = _settings(
        webhook_secret="same-secret",
        admin_api_key="same-secret",
        environment="production",
    )
    with pytest.raises(ValueError):
        settings.validate_required()


def test_validate_required_allows_weak_values_in_development() -> None:
    settings = _settings(
        database_url="postgresql+psycopg2://postgres:postgres@db:5432/contracts",
        webhook_secret="same-secret",
        admin_api_key="same-secret",
        environment="development",
    )
    settings.validate_required()
