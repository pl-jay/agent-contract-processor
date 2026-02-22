from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, MetaData, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ProcessedContract(Base):
    __tablename__ = "processed_contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contract_start_date: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_end_date: Mapped[str] = mapped_column(String(64), nullable=False)
    total_value: Mapped[float] = mapped_column(Float, nullable=False)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_renewal: Mapped[bool] = mapped_column(nullable=False)
    termination_notice_days: Mapped[int] = mapped_column(Integer, nullable=False)
    governing_law: Mapped[str] = mapped_column(String(255), nullable=False)
    extraction_confidence_score: Mapped[float] = mapped_column(Float, nullable=False)

    extracted_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    routing_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    route_decision: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    review_item: Mapped["ReviewQueue | None"] = relationship(
        "ReviewQueue", back_populates="contract", uselist=False
    )


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("processed_contracts.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    contract: Mapped[ProcessedContract] = relationship("ProcessedContract", back_populates="review_item")


class ProcessingLog(Base):
    __tablename__ = "processing_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    contract_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_contracts.id", ondelete="SET NULL"), nullable=True
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
