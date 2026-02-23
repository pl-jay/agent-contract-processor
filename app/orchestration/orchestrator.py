import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NotRequired, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session, sessionmaker

from app.agents.extraction_agent import ExtractionAgent
from app.agents.validation_agent import ValidationAgent
from app.core.schemas import (
    ContractExtraction,
    DocumentMetadata,
    DocumentText,
    RetrievedPolicy,
    RoutingDecision,
    ValidationResult,
)
from app.processing.document_processor import DocumentProcessor
from app.rag.retriever import PolicyRetriever
from app.routing.router import route_contract
from app.services.persistence_service import ContractPersistenceService


class ContractState(TypedDict):
    sender: str
    subject: str
    file_path: str
    doc_text: NotRequired[DocumentText]
    extracted_contract: NotRequired[ContractExtraction]
    retrieved_policies: NotRequired[list[RetrievedPolicy]]
    validation_result: NotRequired[ValidationResult]
    routing_decision: NotRequired[RoutingDecision]
    extraction_usage: NotRequired[dict]
    validation_usage: NotRequired[dict]
    extraction_latency_ms: NotRequired[int]
    validation_latency_ms: NotRequired[int]
    contract_id: NotRequired[int]


class ContractOrchestrator:
    def __init__(
        self,
        document_processor: DocumentProcessor,
        extraction_agent: ExtractionAgent,
        policy_retriever: PolicyRetriever,
        validation_agent: ValidationAgent,
        session_factory: sessionmaker[Session],
    ) -> None:
        self._logger = logging.getLogger(__name__)
        self._document_processor = document_processor
        self._extraction_agent = extraction_agent
        self._policy_retriever = policy_retriever
        self._validation_agent = validation_agent
        self._persistence = ContractPersistenceService(session_factory)
        self._graph = self._compile_graph()

    def run(self, sender: str, subject: str, file_path: str | Path) -> dict:
        pipeline_start = time.perf_counter()
        input_path = Path(file_path)
        state: ContractState = {
            "sender": sender,
            "subject": subject,
            "file_path": str(input_path),
        }

        try:
            result = self._graph.invoke(state)
            route_value: str | None = None
            routing_decision = result.get("routing_decision")
            if isinstance(routing_decision, RoutingDecision):
                route_value = routing_decision.route
            elif isinstance(routing_decision, dict):
                route_value = routing_decision.get("route")

            self._logger.info(
                "Pipeline completed",
                extra={
                    "event": "pipeline_completed",
                    "contract_id": result.get("contract_id"),
                    "route": route_value,
                    "elapsed_ms": int((time.perf_counter() - pipeline_start) * 1000),
                },
            )
            return result
        except Exception as exc:
            self._logger.exception(
                "Pipeline failed",
                extra={"event": "pipeline_failed", "error": str(exc), "file_path": str(input_path)},
            )
            self._persist_failure_log(sender=sender, subject=subject, file_path=str(input_path), error=str(exc))
            raise
        finally:
            self._cleanup_uploaded_file(input_path)

    def _compile_graph(self):
        graph = StateGraph(ContractState)
        graph.add_node("ingest", self._ingest_node)
        graph.add_node("extract", self._extract_node)
        graph.add_node("validate", self._validate_node)
        graph.add_node("route", self._route_node)
        graph.add_node("persist", self._persist_node)

        graph.set_entry_point("ingest")
        graph.add_edge("ingest", "extract")
        graph.add_edge("extract", "validate")
        graph.add_edge("validate", "route")
        graph.add_edge("route", "persist")
        graph.add_edge("persist", END)

        return graph.compile()

    def _ingest_node(self, state: ContractState) -> dict:
        metadata = DocumentMetadata(
            sender=state["sender"],
            subject=state["subject"],
            filename=Path(state["file_path"]).name,
            received_at=datetime.now(timezone.utc),
        )

        doc_text = self._document_processor.extract_document_text(state["file_path"], metadata)
        return {"doc_text": doc_text}

    def _extract_node(self, state: ContractState) -> dict:
        extracted_contract, usage, latency_ms = self._extraction_agent.extract(state["doc_text"])

        self._logger.info(
            "Extraction completed",
            extra={
                "event": "extraction_completed",
                "vendor_name": extracted_contract.vendor_name,
                "confidence_score": extracted_contract.confidence_score,
                "extraction_latency_ms": latency_ms,
                "token_usage": usage,
            },
        )

        return {
            "extracted_contract": extracted_contract,
            "extraction_usage": usage,
            "extraction_latency_ms": latency_ms,
        }

    def _validate_node(self, state: ContractState) -> dict:
        policies = self._policy_retriever.retrieve_relevant_policies(state["extracted_contract"])
        validation, usage, latency_ms = self._validation_agent.validate(
            contract=state["extracted_contract"],
            policies=policies,
        )

        self._logger.info(
            "Validation completed",
            extra={
                "event": "validation_completed",
                "risk_level": validation.risk_level,
                "requires_human_review": validation.requires_human_review,
                "policy_violations": validation.policy_violations,
                "validation_latency_ms": latency_ms,
                "token_usage": usage,
            },
        )

        return {
            "retrieved_policies": policies,
            "validation_result": validation,
            "validation_usage": usage,
            "validation_latency_ms": latency_ms,
        }

    def _route_node(self, state: ContractState) -> dict:
        decision = route_contract(state["extracted_contract"], state["validation_result"])

        self._logger.info(
            "Routing decision created",
            extra={
                "event": "routing_completed",
                "route": decision.route,
                "reasons": decision.reasons,
            },
        )
        return {"routing_decision": decision}

    def _persist_node(self, state: ContractState) -> dict:
        contract_id = self._persistence.persist_success(state)
        return {"contract_id": contract_id}

    def _persist_failure_log(self, sender: str, subject: str, file_path: str, error: str) -> None:
        self._persistence.persist_failure(
            sender=sender,
            subject=subject,
            file_path=file_path,
            error=error,
        )

    def _cleanup_uploaded_file(self, file_path: Path) -> None:
        try:
            file_path.unlink(missing_ok=True)
        except OSError as exc:
            self._logger.warning(
                "Failed to delete uploaded file after processing",
                extra={
                    "event": "uploaded_file_cleanup_failed",
                    "file_path": str(file_path),
                    "error": str(exc),
                },
            )
