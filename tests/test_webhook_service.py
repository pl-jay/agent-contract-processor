from app.core.schemas import RoutingDecision, ValidationResult
from app.services.webhook_service import build_deferred_webhook_response, build_webhook_response


def test_processed_webhook_response_shape() -> None:
    response = build_webhook_response(
        result={
            "contract_id": 123,
            "routing_decision": RoutingDecision(route="auto_approve", reasons=["ok"]),
            "validation_result": ValidationResult(
                policy_violations=[],
                risk_level="low",
                requires_human_review=False,
                rationale="ok",
            ),
        },
        processing_time_ms=321,
    )

    assert response["status"] == "processed"
    assert response["decision"] == "approved"
    assert response["requires_review"] is False
    assert response["contract_id"] == "123"
    assert response["processing_time_ms"] == 321


def test_deferred_webhook_response_shape() -> None:
    response = build_deferred_webhook_response(request_id="req-1", processing_time_ms=50)
    assert response == {
        "status": "accepted",
        "decision": "review",
        "risk_level": "high",
        "requires_review": True,
        "contract_id": "req-1",
        "processing_time_ms": 50,
    }
