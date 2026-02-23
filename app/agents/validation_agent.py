import logging
import re
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import get_settings
from app.core.schemas import ContractExtraction, RetrievedPolicy, ValidationResult


class ValidationAgent:
    def __init__(self, llm: BaseChatModel, max_retries: int):
        # Validation is deterministic by design, but we keep LLM parameters for
        # compatibility with existing dependency wiring and future extension.
        self._llm = llm
        self._max_retries = max_retries
        self._logger = logging.getLogger(__name__)
        self._policy_threshold = get_settings().policy_threshold

    def validate(
        self, contract: ContractExtraction, policies: list[RetrievedPolicy]
    ) -> tuple[ValidationResult, dict[str, Any], int]:
        start = time.perf_counter()
        threshold = self._extract_policy_threshold(policies) or self._policy_threshold
        missing_fields = self._missing_required_fields(contract)
        exceeds_threshold = contract.total_value > threshold

        policy_violations: list[str] = []
        if exceeds_threshold:
            policy_violations.append(
                f"total_value_exceeds_policy_threshold:{contract.total_value}>{threshold}"
            )
        if missing_fields:
            policy_violations.append(f"missing_required_fields:{','.join(missing_fields)}")

        requires_human_review = exceeds_threshold or bool(missing_fields)
        risk_level = "high" if requires_human_review else "low"
        rationale = (
            "Contract requires review due to threshold exceedance or missing required fields."
            if requires_human_review
            else "Contract passed threshold and required field checks."
        )

        result = ValidationResult(
            policy_violations=policy_violations,
            risk_level=risk_level,
            requires_human_review=requires_human_review,
            rationale=rationale,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        return result, {"mode": "deterministic", "llm_configured": self._llm is not None}, latency_ms

    @staticmethod
    def _missing_required_fields(contract: ContractExtraction) -> list[str]:
        missing: list[str] = []

        if not contract.vendor_name.strip():
            missing.append("vendor_name")
        if not contract.contract_start_date.strip():
            missing.append("contract_start_date")
        if not contract.contract_end_date.strip():
            missing.append("contract_end_date")

        return missing

    @staticmethod
    def _extract_policy_threshold(policies: list[RetrievedPolicy]) -> float | None:
        pattern = re.compile(r"(?i)(?:usd|\$)\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
        candidates: list[float] = []

        for policy in policies:
            for match in pattern.finditer(policy.content):
                value = match.group(1).replace(",", "")
                try:
                    parsed = float(value)
                    if parsed > 0:
                        candidates.append(parsed)
                except ValueError:
                    continue

        if not candidates:
            return None
        return min(candidates)
