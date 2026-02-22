from collections.abc import Generator
import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base

logger = logging.getLogger(__name__)


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def get_engine() -> Engine:
    settings = get_settings()
    db_url = settings.resolved_database_url
    if not db_url:
        raise ValueError("DATABASE_URL is required and must be set in the environment")
    connect_args = {"check_same_thread": False} if _is_sqlite(db_url) else {}
    return create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)


engine: Engine | None = None
SessionLocal = sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False)


def _ensure_engine() -> Engine:
    global engine
    if engine is None:
        engine = get_engine()
        SessionLocal.configure(bind=engine)
    return engine


def get_db() -> Generator[Session, None, None]:
    _ensure_engine()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    attempts = 10
    delay_seconds = 2
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            Base.metadata.create_all(bind=_ensure_engine())
            return
        except Exception as exc:  # pragma: no cover - depends on runtime infra
            last_error = exc
            logger.warning(
                "Database init attempt failed",
                extra={
                    "event": "db_init_retry",
                    "attempt": attempt,
                    "max_attempts": attempts,
                    "error": str(exc),
                },
            )
            if attempt < attempts:
                time.sleep(delay_seconds)

    raise RuntimeError(f"Database initialization failed after {attempts} attempts: {last_error}")
