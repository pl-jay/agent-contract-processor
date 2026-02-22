from __future__ import annotations

from datetime import datetime
import json
import math
import re
from typing import Any, get_args, get_origin

from pydantic import BaseModel

_NULLISH = {
    "",
    "-",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "unknown",
    "not specified",
    "not available",
}
_WHITESPACE_RE = re.compile(r"\s+")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_ORDINAL_SUFFIX_RE = re.compile(r"(?<=\d)(st|nd|rd|th)", flags=re.IGNORECASE)
_CURRENCY_WORD_RE = re.compile(
    r"(?i)\b(usd|us\$|dollars?|eur|euro|gbp|pounds?|lkr|rs|inr)\b"
)
_MAGNITUDE_TOKEN_RE = re.compile(
    r"(?i)(k|m|b|thousand|million|billion)\b"
)
_MAGNITUDE = {
    "k": 1_000.0,
    "thousand": 1_000.0,
    "m": 1_000_000.0,
    "million": 1_000_000.0,
    "b": 1_000_000_000.0,
    "billion": 1_000_000_000.0,
}
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
]


def clean_payload_for_model(payload: Any, model: type[BaseModel]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Extraction payload is not a JSON object")

    cleaned: dict[str, Any] = {}
    for field_name, field in model.model_fields.items():
        if field_name not in payload:
            continue
        target_type = _resolve_target_type(field.annotation)
        cleaned[field_name] = _coerce_value(
            field_name=field_name,
            value=payload.get(field_name),
            target_type=target_type,
        )
    return cleaned


def _resolve_target_type(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation

    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(args) == 1:
        return _resolve_target_type(args[0])
    return annotation


def _coerce_value(field_name: str, value: Any, target_type: Any) -> Any:
    if target_type is bool:
        return _to_bool(value)
    if target_type is int:
        as_number = _to_number(value)
        return int(as_number) if as_number is not None else 0
    if target_type is float:
        as_number = _to_number(value)
        return float(as_number) if as_number is not None else 0.0
    if target_type is str:
        return _to_text(value, field_name=field_name)
    return value


def _to_text(value: Any, *, field_name: str) -> str:
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=True)
    else:
        text = str(value)

    text = _WHITESPACE_RE.sub(" ", text).strip()
    if text.lower() in _NULLISH:
        return ""

    if "date" in field_name.lower():
        parsed = _parse_date_to_iso(text)
        if parsed:
            return parsed
    return text


def _to_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None

    text = str(value).strip()
    if not text or text.lower() in _NULLISH:
        return None

    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()

    text = text.replace(",", "")
    text = _CURRENCY_WORD_RE.sub("", text)
    text = text.replace("$", " ")
    text = text.replace("€", " ")
    text = text.replace("£", " ")
    text = _WHITESPACE_RE.sub(" ", text).strip()

    match = _NUMBER_RE.search(text)
    if not match:
        return None

    try:
        parsed = float(match.group(0))
    except ValueError:
        return None

    magnitude_match = _MAGNITUDE_TOKEN_RE.search(text[match.end() :])
    if magnitude_match:
        multiplier = _MAGNITUDE.get(magnitude_match.group(1).lower(), 1.0)
        parsed *= multiplier

    if negative:
        parsed *= -1.0

    return parsed if math.isfinite(parsed) else None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1"}:
            return True
        if normalized in {"false", "no", "n", "0"}:
            return False
    return False


def _parse_date_to_iso(value: str) -> str | None:
    normalized = _ORDINAL_SUFFIX_RE.sub("", value.strip())
    normalized = _WHITESPACE_RE.sub(" ", normalized)
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(normalized, date_format).date().isoformat()
        except ValueError:
            continue
    return None
