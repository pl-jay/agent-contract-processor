import logging
import sys

try:
    from pythonjsonlogger import jsonlogger
except ModuleNotFoundError:  # pragma: no cover - depends on runtime environment
    jsonlogger = None


def configure_logging(log_level: str = "INFO") -> None:
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    if jsonlogger is not None:
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(event)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    if jsonlogger is None:
        root_logger.warning(
            "python-json-logger not installed; using plain-text logs",
            extra={"event": "logger_fallback_plaintext"},
        )
