import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.config import Settings
from app.core.security import verify_admin_api_key


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/review-queue",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def _settings(**overrides: object) -> Settings:
    base = {
        "anthropic_api_key": "test-anthropic",
        "database_url": "sqlite:///./test.db",
        "webhook_secret": "webhook-secret",
        "admin_api_key": "",
        "allowed_origins_raw": "http://localhost:3000",
        "extraction_model": "claude-test",
        "validation_model": "claude-test",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    }
    base.update(overrides)
    return Settings(**base)


def test_admin_api_key_missing_header_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_admin_api_key(request=_request(), x_api_key=None, settings=_settings(admin_api_key="admin"))
    assert exc.value.status_code == 401


def test_admin_api_key_invalid_rejected() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_admin_api_key(request=_request(), x_api_key="wrong", settings=_settings(admin_api_key="admin"))
    assert exc.value.status_code == 401


def test_admin_api_key_missing_configuration_returns_500() -> None:
    with pytest.raises(HTTPException) as exc:
        verify_admin_api_key(
            request=_request(),
            x_api_key="webhook-secret",
            settings=_settings(admin_api_key=""),
        )
    assert exc.value.status_code == 500


def test_admin_api_key_accepts_configured_secret_only() -> None:
    verify_admin_api_key(
        request=_request(),
        x_api_key="admin-secret",
        settings=_settings(admin_api_key="admin-secret"),
    )
