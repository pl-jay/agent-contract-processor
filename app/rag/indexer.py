import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from app.core.config import get_settings
from app.processing.pdf_utils import load_pymupdf_module
from app.rag.chroma_settings import build_chroma_client_settings
from app.providers import build_embeddings

fitz = load_pymupdf_module()


class PolicyIndexer:
    def __init__(self, embeddings: Embeddings | None = None) -> None:
        self._settings = get_settings()
        self._embeddings = embeddings or build_embeddings(self._settings)
        self._logger = logging.getLogger(__name__)

    def build_index(self, reset: bool = False) -> int:
        settings = self._settings
        settings.chroma_persist_dir.mkdir(parents=True, exist_ok=True)
        client_settings = build_chroma_client_settings(settings.chroma_persist_dir)

        documents = self._load_documents(settings.policy_dir)
        if not documents:
            raise ValueError(f"No policy documents found in {settings.policy_dir}")

        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=500,
            chunk_overlap=50,
        )
        chunks = splitter.split_documents(documents)

        vector_store = Chroma(
            collection_name=settings.chroma_collection,
            embedding_function=self._embeddings,
            persist_directory=str(settings.chroma_persist_dir),
            client_settings=client_settings,
        )

        if reset:
            try:
                vector_store.delete_collection()
            except Exception:
                # Collection may not exist on first run.
                pass
            vector_store = Chroma(
                collection_name=settings.chroma_collection,
                embedding_function=self._embeddings,
                persist_directory=str(settings.chroma_persist_dir),
                client_settings=client_settings,
            )

        vector_store.add_documents(chunks)

        self._logger.info(
            "Indexed policy documents",
            extra={
                "event": "policy_indexed",
                "documents": len(documents),
                "chunks": len(chunks),
            },
        )
        return len(chunks)

    def _load_documents(self, policy_dir: Path) -> list[Document]:
        docs: list[Document] = []

        for file_path in policy_dir.rglob("*"):
            if not file_path.is_file():
                continue

            suffix = file_path.suffix.lower()
            if suffix not in {".txt", ".md", ".pdf"}:
                continue

            if suffix == ".pdf":
                content = self._extract_pdf_text(file_path)
            else:
                content = file_path.read_text(encoding="utf-8", errors="ignore")

            if not content.strip():
                continue

            docs.append(
                Document(
                    page_content=content,
                    metadata={"source": str(file_path)},
                )
            )

        return docs

    @staticmethod
    def _extract_pdf_text(file_path: Path) -> str:
        with fitz.open(file_path) as doc:
            return "\n".join(page.get_text("text") for page in doc)


def main() -> None:
    indexer = PolicyIndexer()
    indexed_chunks = indexer.build_index(reset=True)
    print(f"Indexed {indexed_chunks} chunks.")


if __name__ == "__main__":
    main()
