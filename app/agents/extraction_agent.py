import logging
import re
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.errors import ExtractionError
from app.core.schemas import ContractExtraction, DocumentText
from app.processing.data_cleaner import clean_payload_for_model
from app.services.structured_llm import run_structured_llm


class ExtractionAgent:
    _KEYWORD_PATTERN = re.compile(
        r"(?i)\b(vendor|supplier|agreement|contract|effective|start|end|term|expires|amount|value|total|usd|\$)\b"
    )

    def __init__(self, llm: BaseChatModel, max_retries: int, max_input_chars: int = 24000):
        self._logger = logging.getLogger(__name__)
        self._max_retries = max_retries
        self._llm = llm
        self._max_input_chars = max(max_input_chars, 4000)

    def extract(self, document: DocumentText) -> tuple[ContractExtraction, dict[str, Any], int]:
        bounded_text = self._build_bounded_input_text(document.raw_text)
        system_prompt = (
            "You extract contract fields and return STRICT JSON only with these keys: "
            "vendor_name, contract_start_date, contract_end_date, total_value. "
            "Do not add extra keys. Return JSON only with no prose or markdown."
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "Extract fields from this contract text and return strict JSON only:\n\n"
                    f"{bounded_text}"
                )
            ),
        ]

        def _parse_output(parsed: dict[str, Any]) -> ContractExtraction:
            cleaned = clean_payload_for_model(parsed, ContractExtraction)
            normalized = self._normalize_payload(cleaned)
            return ContractExtraction.model_validate(normalized)

        return run_structured_llm(
            self._llm,
            messages,
            max_retries=self._max_retries,
            parse_output=_parse_output,
            logger=self._logger,
            parse_failure_event="extraction_parse_failure",
            parse_failure_log_message="Extraction parse failure",
            not_found_message=(
                "Configured EXTRACTION_MODEL is not available for this Anthropic API key. "
                "Set EXTRACTION_MODEL to a model id available in your Anthropic account."
            ),
            error_type=ExtractionError,
            final_error_prefix="Extraction failed",
        )

    @staticmethod
    def _normalize_payload(payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Extraction payload is not a JSON object")

        normalized = dict(payload)

        normalized.setdefault("vendor_name", "")
        normalized.setdefault("contract_start_date", "")
        normalized.setdefault("contract_end_date", "")
        normalized.setdefault("total_value", 0)

        for field in (
            "vendor_name",
            "contract_start_date",
            "contract_end_date",
        ):
            value = normalized.get(field)
            if value is None:
                normalized[field] = ""

        total_value = normalized.get("total_value")
        if total_value is None or total_value == "":
            normalized["total_value"] = 0.0

        # Derive confidence deterministically from completeness of essential fields.
        completeness = 0
        if normalized["vendor_name"]:
            completeness += 1
        if normalized["contract_start_date"]:
            completeness += 1
        if normalized["contract_end_date"]:
            completeness += 1
        if isinstance(normalized["total_value"], (int, float)) and normalized["total_value"] > 0:
            completeness += 1
        normalized["confidence_score"] = round(completeness / 4, 2)

        return normalized

    def _build_bounded_input_text(self, text: str) -> str:
        normalized = text.strip()
        if len(normalized) <= self._max_input_chars:
            return normalized

        head_budget = int(self._max_input_chars * 0.35)
        tail_budget = int(self._max_input_chars * 0.2)
        middle_budget = self._max_input_chars - head_budget - tail_budget - 128
        middle_budget = max(middle_budget, int(self._max_input_chars * 0.2))

        keyword_middle = self._select_keyword_sections(normalized, middle_budget)
        bounded = (
            f"{normalized[:head_budget]}\n\n"
            "[...TRUNCATED FOR TOKEN LIMIT...]\n\n"
            f"{keyword_middle}\n\n"
            "[...END TRUNCATED SECTION...]\n\n"
            f"{normalized[-tail_budget:]}"
        )

        if len(bounded) > self._max_input_chars:
            bounded = bounded[: self._max_input_chars]

        self._logger.warning(
            "Contract text truncated before extraction",
            extra={
                "event": "extraction_input_truncated",
                "original_chars": len(normalized),
                "bounded_chars": len(bounded),
                "max_input_chars": self._max_input_chars,
            },
        )
        return bounded

    def _select_keyword_sections(self, text: str, budget: int) -> str:
        sections = re.split(r"\n\s*\n", text)
        chosen: list[str] = []
        used = 0

        for section in sections:
            chunk = section.strip()
            if not chunk or not self._KEYWORD_PATTERN.search(chunk):
                continue
            chunk = chunk[:1200]
            if used + len(chunk) + 2 > budget:
                break
            chosen.append(chunk)
            used += len(chunk) + 2

        if chosen:
            return "\n\n".join(chosen)

        mid_start = max((len(text) // 2) - (budget // 2), 0)
        return text[mid_start : mid_start + budget]
