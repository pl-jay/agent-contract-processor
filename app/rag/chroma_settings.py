from __future__ import annotations

from pathlib import Path

from chromadb.config import Settings as ChromaClientSettings


def build_chroma_client_settings(persist_directory: str | Path) -> ChromaClientSettings:
    return ChromaClientSettings(
        is_persistent=True,
        persist_directory=str(persist_directory),
        anonymized_telemetry=False,
        chroma_product_telemetry_impl="app.rag.chroma_telemetry.NoOpTelemetryClient",
        chroma_telemetry_impl="app.rag.chroma_telemetry.NoOpTelemetryClient",
    )
