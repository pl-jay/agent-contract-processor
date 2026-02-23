from app.agents.validation_agent import ValidationAgent
from app.core.schemas import RetrievedPolicy


def test_extract_policy_threshold_parses_usd_values() -> None:
    policies = [
        RetrievedPolicy(
            source="policy.md",
            content="Contracts above USD 500,000 require CFO approval.",
        ),
        RetrievedPolicy(
            source="policy-2.md",
            content="Escalate if amount exceeds $700000.",
        ),
    ]

    threshold = ValidationAgent._extract_policy_threshold(policies)
    assert threshold == 500000.0
