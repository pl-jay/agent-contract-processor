from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.schemas import RoutingDecision, ValidationResult
from app.db.models import ProcessedContract, ProcessingLog, ReviewQueue


class ContractPersistenceService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def persist_success(self, state: dict[str, Any]) -> int:
        with self._session_factory() as session:
            contract = ProcessedContract(
                sender=state["sender"],
                subject=state["subject"],
                file_path=state["file_path"],
                vendor_name=state["extracted_contract"].vendor_name,
                contract_start_date=state["extracted_contract"].contract_start_date,
                contract_end_date=state["extracted_contract"].contract_end_date,
                total_value=state["extracted_contract"].total_value,
                payment_terms_days=0,
                auto_renewal=False,
                termination_notice_days=0,
                governing_law="",
                extraction_confidence_score=state["extracted_contract"].confidence_score,
                extracted_payload=state["extracted_contract"].model_dump(mode="json"),
                validation_payload=state["validation_result"].model_dump(mode="json"),
                routing_payload=state["routing_decision"].model_dump(mode="json"),
                route_decision=state["routing_decision"].route,
                status="approved" if state["routing_decision"].route == "auto_approve" else "pending_review",
            )
            session.add(contract)
            session.flush()

            if state["routing_decision"].route == "review_queue":
                queue_item = ReviewQueue(
                    contract_id=contract.id,
                    status="pending",
                    reason="; ".join(state["routing_decision"].reasons),
                )
                session.add(queue_item)

            session.add_all(
                [
                    ProcessingLog(
                        contract_id=contract.id,
                        stage="extract",
                        message="Extraction completed",
                        payload={
                            "latency_ms": state.get("extraction_latency_ms", 0),
                            "token_usage": state.get("extraction_usage", {}),
                        },
                    ),
                    ProcessingLog(
                        contract_id=contract.id,
                        stage="validate",
                        message="Validation completed",
                        payload={
                            "latency_ms": state.get("validation_latency_ms", 0),
                            "token_usage": state.get("validation_usage", {}),
                            "result": state["validation_result"].model_dump(mode="json"),
                        },
                    ),
                    ProcessingLog(
                        contract_id=contract.id,
                        stage="route",
                        message="Routing completed",
                        payload=state["routing_decision"].model_dump(mode="json"),
                    ),
                ]
            )

            session.commit()
            return int(contract.id)

    def persist_failure(self, sender: str, subject: str, file_path: str, error: str) -> None:
        with self._session_factory() as session:
            session.add(
                ProcessingLog(
                    contract_id=None,
                    stage="pipeline_error",
                    message="Pipeline failed",
                    payload={
                        "sender": sender,
                        "subject": subject,
                        "file_path": file_path,
                        "error": error,
                    },
                )
            )
            session.commit()

    def persist_failure_as_review(self, sender: str, subject: str, file_path: str, error: str) -> int:
        reasons = ["pipeline_error_fallback_to_review"]
        validation = ValidationResult(
            policy_violations=[f"pipeline_error:{error}"],
            risk_level="high",
            requires_human_review=True,
            rationale="Pipeline failed before full validation; contract routed to review queue.",
        )
        routing = RoutingDecision(route="review_queue", reasons=reasons)

        with self._session_factory() as session:
            contract = ProcessedContract(
                sender=sender,
                subject=subject,
                file_path=file_path,
                vendor_name="",
                contract_start_date="",
                contract_end_date="",
                total_value=0.0,
                payment_terms_days=0,
                auto_renewal=False,
                termination_notice_days=0,
                governing_law="",
                extraction_confidence_score=0.0,
                extracted_payload={"error": error},
                validation_payload=validation.model_dump(mode="json"),
                routing_payload=routing.model_dump(mode="json"),
                route_decision=routing.route,
                status="pending_review",
            )
            session.add(contract)
            session.flush()

            session.add(
                ReviewQueue(
                    contract_id=contract.id,
                    status="pending",
                    reason="; ".join(reasons),
                )
            )
            session.add(
                ProcessingLog(
                    contract_id=contract.id,
                    stage="pipeline_error",
                    message="Pipeline failed and was routed to review queue",
                    payload={
                        "sender": sender,
                        "subject": subject,
                        "file_path": file_path,
                        "error": error,
                    },
                )
            )
            session.commit()
            return int(contract.id)
