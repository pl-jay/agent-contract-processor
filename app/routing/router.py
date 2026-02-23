from app.core.schemas import ContractExtraction, RoutingDecision, ValidationResult


def route_contract(
    contract: ContractExtraction,
    validation: ValidationResult,
    policy_threshold: float | None = None,
) -> RoutingDecision:
    reasons: list[str] = []

    if contract.confidence_score < 0.8:
        reasons.append("extraction_confidence_below_threshold")

    if validation.requires_human_review:
        reasons.append("validation_requires_human_review")
        reasons.extend([f"validation:{violation}" for violation in validation.policy_violations])

    # Optional explicit threshold override is only used for tests/diagnostics.
    if policy_threshold is not None and contract.total_value > policy_threshold:
        reasons.append(
            f"total_value_exceeds_policy_threshold:{contract.total_value}>{policy_threshold}"
        )

    if reasons:
        return RoutingDecision(route="review_queue", reasons=reasons)

    return RoutingDecision(route="auto_approve", reasons=["meets_auto_approval_rules"])
