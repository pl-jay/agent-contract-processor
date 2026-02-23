from app.core.schemas import ContractExtraction, ValidationResult
from app.routing.router import route_contract


def _validation(*, requires_human_review: bool = False) -> ValidationResult:
    return ValidationResult(
        policy_violations=["missing_required_fields:vendor_name"] if requires_human_review else [],
        risk_level="high" if requires_human_review else "low",
        requires_human_review=requires_human_review,
        rationale="ok",
    )


def test_route_to_review_on_low_confidence() -> None:
    contract = ContractExtraction(
        vendor_name="Vendor",
        contract_start_date="2026-01-01",
        contract_end_date="2027-01-01",
        total_value=1000.0,
        confidence_score=0.7,
    )
    decision = route_contract(contract, _validation(), policy_threshold=500000.0)
    assert decision.route == "review_queue"


def test_route_to_review_on_threshold_exceedance() -> None:
    contract = ContractExtraction(
        vendor_name="Vendor",
        contract_start_date="2026-01-01",
        contract_end_date="2027-01-01",
        total_value=2000.0,
        confidence_score=0.9,
    )
    decision = route_contract(contract, _validation(), policy_threshold=1000.0)
    assert decision.route == "review_queue"


def test_route_to_auto_approve_when_rules_pass() -> None:
    contract = ContractExtraction(
        vendor_name="Vendor",
        contract_start_date="2026-01-01",
        contract_end_date="2027-01-01",
        total_value=1000.0,
        confidence_score=0.9,
    )
    decision = route_contract(contract, _validation(), policy_threshold=5000.0)
    assert decision.route == "auto_approve"


def test_route_to_review_when_validation_requires_human_review() -> None:
    contract = ContractExtraction(
        vendor_name="Vendor",
        contract_start_date="2026-01-01",
        contract_end_date="2027-01-01",
        total_value=1000.0,
        confidence_score=0.95,
    )
    decision = route_contract(contract, _validation(requires_human_review=True))
    assert decision.route == "review_queue"
