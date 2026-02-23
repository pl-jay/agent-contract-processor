import json
import time
from typing import Any, Callable, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import ValidationError

try:
    import anthropic
except ModuleNotFoundError:  # pragma: no cover - depends on runtime environment
    anthropic = None

T = TypeVar("T")


def run_structured_llm(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    *,
    max_retries: int,
    parse_output: Callable[[dict[str, Any]], T],
    logger: Any,
    parse_failure_event: str,
    parse_failure_log_message: str,
    not_found_message: str,
    error_type: type[Exception],
    final_error_prefix: str = "Failed",
) -> tuple[T, dict[str, Any], int]:
    start = time.perf_counter()
    last_error: Exception | None = None
    usage: dict[str, Any] = {}

    for attempt in range(1, max_retries + 1):
        try:
            response = llm.invoke(messages)
            usage = extract_usage(response)
            payload = extract_json_text(response.content)
            parsed = json.loads(payload)
            result = parse_output(parsed)
            latency_ms = int((time.perf_counter() - start) * 1000)
            return result, usage, latency_ms
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            logger.warning(
                parse_failure_log_message,
                extra={"event": parse_failure_event, "attempt": attempt, "error": str(exc)},
            )
        except Exception as exc:
            if _is_model_not_found_error(exc):
                raise error_type(not_found_message) from exc
            raise

    raise error_type(f"{final_error_prefix} after {max_retries} attempts: {last_error}")


def extract_json_text(content: Any) -> str:
    if not isinstance(content, str):
        raise ValueError("LLM response content is not a string")

    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")

    return cleaned[start : end + 1]


def extract_usage(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage_metadata", None)
    if isinstance(usage, dict):
        return usage

    metadata = getattr(response, "response_metadata", None)
    if isinstance(metadata, dict) and isinstance(metadata.get("token_usage"), dict):
        return metadata["token_usage"]

    return {}


def _is_model_not_found_error(exc: Exception) -> bool:
    if anthropic is not None and isinstance(exc, anthropic.NotFoundError):
        return "model" in str(exc).lower()
    return exc.__class__.__name__ == "NotFoundError" and "model" in str(exc).lower()
