import threading

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from app.core.config import Settings
from app.core.schemas import ContractExtraction, RetrievedPolicy
from app.providers import build_embeddings
from app.rag.chroma_settings import build_chroma_client_settings


class PolicyRetriever:
    def __init__(self, settings: Settings, embeddings: Embeddings | None = None):
        self._settings = settings
        self._embeddings = embeddings
        self._vector_store: Chroma | None = None
        self._vector_store_lock = threading.Lock()
        self._k = settings.retrieval_k

    def retrieve_relevant_policies(self, contract_json: ContractExtraction) -> list[RetrievedPolicy]:
        vector_store = self._get_vector_store()
        query = self._build_query(contract_json)
        docs = vector_store.similarity_search(query, k=self._k)

        return [
            RetrievedPolicy(
                source=str(doc.metadata.get("source", "unknown")),
                content=doc.page_content,
            )
            for doc in docs
        ]

    def _get_vector_store(self) -> Chroma:
        if self._vector_store is not None:
            return self._vector_store

        with self._vector_store_lock:
            if self._vector_store is not None:
                return self._vector_store

            try:
                embeddings = self._embeddings or build_embeddings(self._settings)
                client_settings = build_chroma_client_settings(self._settings.chroma_persist_dir)
                self._vector_store = Chroma(
                    collection_name=self._settings.chroma_collection,
                    embedding_function=embeddings,
                    persist_directory=str(self._settings.chroma_persist_dir),
                    client_settings=client_settings,
                )
                return self._vector_store
            except Exception as exc:
                raise RuntimeError(
                    "Failed to initialize embedding/vector store. "
                    "If running in Docker with restricted network, either fix DNS/network access to "
                    "huggingface.co or pre-cache the model and set EMBEDDING_LOCAL_FILES_ONLY=true."
                ) from exc

    @staticmethod
    def _build_query(contract: ContractExtraction) -> str:
        return (
            f"Vendor: {contract.vendor_name}; "
            f"Contract start date: {contract.contract_start_date}; "
            f"Contract end date: {contract.contract_end_date}; "
            f"Total value: {contract.total_value}; "
            "Retrieve policies relevant to total value approval thresholds and required contract fields."
        )
