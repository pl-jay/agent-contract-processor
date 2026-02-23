from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.errors import DocumentProcessingError
from app.core.schemas import ContractExtraction, RetrievedPolicy, ValidationResult
from app.db.models import Base, ProcessedContract, ReviewQueue
from app.orchestration.orchestrator import ContractOrchestrator


class _FailingDocumentProcessor:
    def extract_document_text(self, file_path, metadata):  # noqa: ANN001
        _ = file_path, metadata
        raise DocumentProcessingError("PDF did not contain extractable text")


class _DummyExtractionAgent:
    def extract(self, document):  # noqa: ANN001
        _ = document
        return (
            ContractExtraction(
                vendor_name="Vendor",
                contract_start_date="2026-01-01",
                contract_end_date="2027-01-01",
                total_value=1000.0,
                confidence_score=1.0,
            ),
            {},
            1,
        )


class _DummyPolicyRetriever:
    def retrieve_relevant_policies(self, contract_json):  # noqa: ANN001
        _ = contract_json
        return [RetrievedPolicy(source="test", content="USD 500000")]


class _DummyValidationAgent:
    def validate(self, contract, policies):  # noqa: ANN001
        _ = contract, policies
        return (
            ValidationResult(
                policy_violations=[],
                risk_level="low",
                requires_human_review=False,
                rationale="ok",
            ),
            {},
            1,
        )


def test_orchestrator_routes_document_processing_error_to_review_queue() -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    orchestrator = ContractOrchestrator(
        document_processor=_FailingDocumentProcessor(),
        extraction_agent=_DummyExtractionAgent(),
        policy_retriever=_DummyPolicyRetriever(),
        validation_agent=_DummyValidationAgent(),
        session_factory=SessionLocal,
    )

    with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"%PDF- demo")
        file_path = tmp.name

    result = orchestrator.run("sender@test.com", "subject", file_path)

    assert result["routing_decision"].route == "review_queue"
    assert result["validation_result"].requires_human_review is True
    assert isinstance(result["contract_id"], int)

    with SessionLocal() as session:
        contract = session.get(ProcessedContract, result["contract_id"])
        assert contract is not None
        assert contract.route_decision == "review_queue"
        assert contract.status == "pending_review"

        queue_item = session.query(ReviewQueue).filter(ReviewQueue.contract_id == contract.id).one_or_none()
        assert queue_item is not None
        assert queue_item.status == "pending"

    Path(file_path).unlink(missing_ok=True)
