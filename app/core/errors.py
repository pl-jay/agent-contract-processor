class DocumentProcessingError(Exception):
    """Raised when a PDF cannot be parsed correctly."""


class ExtractionError(Exception):
    """Raised when structured contract extraction fails after retries."""


class ValidationAgentError(Exception):
    """Raised when validation output parsing fails after retries."""
