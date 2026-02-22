from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.extraction_agent import ExtractionAgent
from app.agents.validation_agent import ValidationAgent
from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.logging.logging_config import configure_logging
from app.orchestration.orchestrator import ContractOrchestrator
from app.processing.document_processor import DocumentProcessor
from app.providers import build_chat_model
from app.rag.retriever import PolicyRetriever
from app.routers.email_router import build_email_router
from app.routers.review_router import router as review_router
from app.services.pipeline_executor import PipelineExecutor


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    try:
        settings.validate_required()
    except ValueError as exc:
        logger.error(
            "Startup configuration validation failed",
            extra={"event": "startup_config_invalid", "error": str(exc)},
        )
        raise RuntimeError(str(exc)) from exc

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
    settings.embedding_cache_dir.mkdir(parents=True, exist_ok=True)

    init_db()

    extraction_chat_model = build_chat_model(settings, model_name=settings.resolved_extraction_model)
    validation_chat_model = build_chat_model(settings, model_name=settings.resolved_validation_model)

    logger.info(
        "Model providers configured",
        extra={
            "event": "provider_configured",
            "llm_provider": "anthropic",
            "extraction_model": settings.resolved_extraction_model,
            "validation_model": settings.resolved_validation_model,
            "embedding_provider": "local_huggingface",
            "embedding_model": settings.embedding_model,
        },
    )

    orchestrator = ContractOrchestrator(
        document_processor=DocumentProcessor(),
        extraction_agent=ExtractionAgent(
            llm=extraction_chat_model,
            max_retries=settings.extraction_max_retries,
            max_input_chars=settings.extraction_max_input_chars,
        ),
        policy_retriever=PolicyRetriever(settings),
        validation_agent=ValidationAgent(
            llm=validation_chat_model,
            max_retries=settings.validation_max_retries,
        ),
        session_factory=SessionLocal,
    )
    pipeline_executor = PipelineExecutor(
        orchestrator=orchestrator,
        max_workers=settings.pipeline_workers,
        wait_timeout_seconds=settings.webhook_sync_timeout_seconds,
        idempotency_enabled=settings.webhook_idempotency_enabled,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info(
            "API startup complete",
            extra={"event": "api_startup_complete", "service": settings.app_name},
        )
        logger.info(
            "CORS configured",
            extra={
                "event": "cors_configured",
                "allowed_origins": settings.allowed_origins,
            },
        )
        yield
        pipeline_executor.shutdown()

    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(
        build_email_router(
            pipeline_executor=pipeline_executor,
            upload_dir=settings.upload_dir,
            max_upload_size_bytes=settings.max_upload_size_bytes,
        )
    )
    app.include_router(review_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
