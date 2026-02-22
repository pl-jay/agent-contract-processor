from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentMetadata(BaseModel):
    sender: str
    subject: str
    filename: str
    received_at: datetime

    model_config = ConfigDict(extra="forbid")


class DocumentText(BaseModel):
    raw_text: str = Field(min_length=1)
    metadata: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


class ContractExtraction(BaseModel):
    vendor_name: str
    contract_start_date: str
    contract_end_date: str
    total_value: float
    confidence_score: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class RetrievedPolicy(BaseModel):
    source: str
    content: str

    model_config = ConfigDict(extra="forbid")


class ValidationResult(BaseModel):
    policy_violations: list[str]
    risk_level: Literal["low", "high"]
    requires_human_review: bool
    rationale: str

    model_config = ConfigDict(extra="forbid")


class RoutingDecision(BaseModel):
    route: Literal["review_queue", "auto_approve"]
    reasons: list[str]

    model_config = ConfigDict(extra="forbid")
