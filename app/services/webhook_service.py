from __future__ import annotations

from typing import Any

from app.core.schemas import RoutingDecision, ValidationResult


def build_webhook_response(result: dict[str, Any], processing_time_ms: int) -> dict[str, Any]:
    routing_decision = result.get("routing_decision")
    validation_result = result.get("validation_result")

    route = _extract_route(routing_decision)
    risk_level = _extract_risk_level(validation_result)

    decision = "approved" if route == "auto_approve" else "review"
    requires_review = decision == "review"

    return {
        "status": "processed",
        "decision": decision,
        "risk_level": risk_level,
        "requires_review": requires_review,
        "contract_id": str(result.get("contract_id", "")),
        "processing_time_ms": processing_time_ms,
    }


def build_deferred_webhook_response(request_id: str, processing_time_ms: int) -> dict[str, Any]:
    # Conservative fallback when background execution continues beyond sync timeout.
    return {
        "status": "accepted",
        "decision": "review",
        "risk_level": "high",
        "requires_review": True,
        "contract_id": request_id,
        "processing_time_ms": processing_time_ms,
    }


def _extract_route(routing_decision: Any) -> str:
    if isinstance(routing_decision, RoutingDecision):
        return routing_decision.route
    if isinstance(routing_decision, dict):
        value = routing_decision.get("route")
        if isinstance(value, str):
            return value
    return "review_queue"


def _extract_risk_level(validation_result: Any) -> str:
    if isinstance(validation_result, ValidationResult):
        return validation_result.risk_level
    if isinstance(validation_result, dict):
        value = validation_result.get("risk_level")
        if value in {"low", "high"}:
            return value
    return "high"
