from app.core.config import get_settings
from app.core.schemas import ContractExtraction, RoutingDecision, ValidationResult


def route_contract(
    contract: ContractExtraction,
    validation: ValidationResult,
    policy_threshold: float | None = None,
) -> RoutingDecision:
    _ = validation  # preserved signature; routing is deterministic and independent from LLM output
    threshold = policy_threshold if policy_threshold is not None else get_settings().policy_threshold
    reasons: list[str] = []

    if contract.confidence_score < 0.8:
        reasons.append("extraction_confidence_below_threshold")

    if contract.total_value > threshold:
        reasons.append(
            f"total_value_exceeds_policy_threshold:{contract.total_value}>{threshold}"
        )

    if reasons:
        return RoutingDecision(route="review_queue", reasons=reasons)

    return RoutingDecision(route="auto_approve", reasons=["meets_auto_approval_rules"])
