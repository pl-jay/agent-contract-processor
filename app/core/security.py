import logging
import secrets

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _verify_api_key(
    request: Request,
    x_api_key: str | None,
    expected_secret: str,
    missing_secret_event: str,
    unauthorized_missing_event: str,
    unauthorized_invalid_event: str,
    missing_secret_message: str,
) -> None:
    if not expected_secret:
        logger.error(
            missing_secret_message,
            extra={"event": missing_secret_event},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication is not configured",
        )

    if not x_api_key:
        logger.warning(
            "Unauthorized webhook request: missing API key",
            extra={
                "event": unauthorized_missing_event,
                "client_host": request.client.host if request.client else None,
                "path": request.url.path,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    if not secrets.compare_digest(x_api_key, expected_secret):
        logger.warning(
            "Unauthorized webhook request: invalid API key",
            extra={
                "event": unauthorized_invalid_event,
                "client_host": request.client.host if request.client else None,
                "path": request.url.path,
            },
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def verify_webhook_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
    settings: Settings = Depends(get_settings),
) -> None:
    _verify_api_key(
        request=request,
        x_api_key=x_api_key,
        expected_secret=settings.webhook_secret.strip(),
        missing_secret_event="webhook_secret_missing",
        unauthorized_missing_event="webhook_unauthorized_missing_key",
        unauthorized_invalid_event="webhook_unauthorized_invalid_key",
        missing_secret_message="Webhook secret missing in environment",
    )


def verify_admin_api_key(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
    settings: Settings = Depends(get_settings),
) -> None:
    _verify_api_key(
        request=request,
        x_api_key=x_api_key,
        expected_secret=settings.resolved_admin_api_key,
        missing_secret_event="admin_secret_missing",
        unauthorized_missing_event="admin_unauthorized_missing_key",
        unauthorized_invalid_event="admin_unauthorized_invalid_key",
        missing_secret_message="Admin API key missing in environment",
    )
