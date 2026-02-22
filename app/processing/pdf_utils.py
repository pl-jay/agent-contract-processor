from __future__ import annotations


def load_pymupdf_module():
    """Return a PyMuPDF-compatible module as `fitz`.

    Supports both historical `import fitz` and newer `import pymupdf` package names.
    """
    try:
        import fitz

        return fitz
    except ModuleNotFoundError:
        try:
            import pymupdf as fitz

            return fitz
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "PyMuPDF is not installed in the active environment. "
                "Install with: pip install PyMuPDF"
            ) from exc
