import pytest

from app.core.config import Settings


def _settings(**overrides: object) -> Settings:
    base = {
        "anthropic_api_key": "test-anthropic",
        "database_url": "sqlite:///./test.db",
        "webhook_secret": "test-secret",
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


def test_validate_required_passes_with_all_required_values() -> None:
    settings = _settings()
    settings.validate_required()
