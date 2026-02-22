from __future__ import annotations

from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpTelemetryClient(ProductTelemetryClient):
    """Disable Chroma product telemetry calls in local/runtime environments."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:  # noqa: ARG002
        return None
