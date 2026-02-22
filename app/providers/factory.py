from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings


class ProviderConfigurationError(ValueError):
    """Raised when provider env configuration is invalid."""


def build_chat_model(settings: Settings, model_name: str | None = None) -> BaseChatModel:
    from langchain_anthropic import ChatAnthropic

    api_key = settings.resolved_llm_api_key
    resolved_model = (model_name or "").strip()
    if not api_key:
        raise ProviderConfigurationError(
            "Anthropic LLM requires ANTHROPIC_API_KEY or LLM_API_KEY"
        )
    if not resolved_model:
        raise ProviderConfigurationError(
            "Model id is required and must be a valid Anthropic model id."
        )

    return ChatAnthropic(
        model=resolved_model,
        temperature=0,
        timeout=settings.llm_timeout_seconds,
        api_key=api_key,
    )


def build_embeddings(settings: Settings) -> Embeddings:
    from langchain_huggingface import HuggingFaceEmbeddings
    if not settings.embedding_model.strip():
        raise ProviderConfigurationError(
            "EMBEDDING_MODEL is required for RAG retrieval."
        )

    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        cache_folder=str(settings.embedding_cache_dir),
        model_kwargs={
            "device": settings.embedding_device,
            "local_files_only": settings.embedding_local_files_only,
        },
        encode_kwargs={"normalize_embeddings": True},
    )
