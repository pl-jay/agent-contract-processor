import re
import time
import unicodedata
from pathlib import Path

from app.core.errors import DocumentProcessingError
from app.core.schemas import DocumentMetadata, DocumentText
from app.processing.pdf_utils import load_pymupdf_module

fitz = load_pymupdf_module()


class DocumentProcessor:
    def extract_document_text(self, file_path: str | Path, metadata: DocumentMetadata) -> DocumentText:
        path = Path(file_path)
        start = time.perf_counter()

        if not path.exists():
            raise DocumentProcessingError(f"File not found: {path}")

        try:
            pages: list[str] = []
            with fitz.open(path) as doc:
                for page in doc:
                    pages.append(page.get_text("text"))
        except (fitz.FileDataError, RuntimeError, ValueError) as exc:
            raise DocumentProcessingError("Invalid or corrupted PDF file") from exc

        raw_text = "\n".join(pages).strip()
        if not raw_text:
            raise DocumentProcessingError("PDF did not contain extractable text")

        normalized = self._normalize_text(raw_text)
        extraction_ms = int((time.perf_counter() - start) * 1000)

        return DocumentText(
            raw_text=normalized,
            metadata={
                **metadata.model_dump(mode="json"),
                "source_file": str(path),
                "extraction_ms": extraction_ms,
            },
        )

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = unicodedata.normalize("NFKC", text)
        text = re.sub(r"[\t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ ]{2,}", " ", text)
        return text.strip()
