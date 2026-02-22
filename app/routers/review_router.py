from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_admin_api_key
from app.db.models import ProcessedContract, ReviewQueue
from app.db.session import get_db


router = APIRouter(prefix="", tags=["review"], dependencies=[Depends(verify_admin_api_key)])


@router.get("/approved-contracts")
def get_approved_contracts(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    items = db.execute(
        select(ProcessedContract)
        .where(ProcessedContract.status == "approved")
        .order_by(ProcessedContract.updated_at.desc(), ProcessedContract.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()

    return {
        "count": len(items),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "contract_id": contract.id,
                "status": contract.status,
                "route_decision": contract.route_decision,
                "sender": contract.sender,
                "subject": contract.subject,
                "vendor_name": contract.vendor_name,
                "total_value": contract.total_value,
                "governing_law": contract.governing_law,
                "extraction_confidence_score": contract.extraction_confidence_score,
                "risk_level": contract.validation_payload.get("risk_level"),
                "policy_violations": contract.validation_payload.get("policy_violations", []),
                "approved_at": contract.updated_at,
                "created_at": contract.created_at,
            }
            for contract in items
        ],
    }


@router.get("/review-queue")
def get_review_queue(db: Session = Depends(get_db)) -> list[dict]:
    items = db.execute(
        select(ReviewQueue, ProcessedContract)
        .join(ProcessedContract, ReviewQueue.contract_id == ProcessedContract.id)
        .where(ReviewQueue.status == "pending")
        .order_by(ReviewQueue.created_at.asc())
    ).all()

    return [
        {
            "review_id": review.id,
            "contract_id": contract.id,
            "status": review.status,
            "reason": review.reason,
            "sender": contract.sender,
            "subject": contract.subject,
            "vendor_name": contract.vendor_name,
            "risk": contract.validation_payload.get("risk_level"),
            "violations": contract.validation_payload.get("policy_violations", []),
            "created_at": review.created_at,
        }
        for review, contract in items
    ]


@router.post("/approve/{id}")
def approve_review(id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(ReviewQueue, id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")
    if review.status != "pending":
        raise HTTPException(status_code=400, detail="Review item is not pending")

    contract = db.get(ProcessedContract, review.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Associated contract not found")

    review.status = "approved"
    review.resolved_at = datetime.now(timezone.utc)
    contract.status = "approved"
    db.commit()

    return {"status": "approved", "review_id": id, "contract_id": contract.id}


@router.post("/reject/{id}")
def reject_review(id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(ReviewQueue, id)
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")
    if review.status != "pending":
        raise HTTPException(status_code=400, detail="Review item is not pending")

    contract = db.get(ProcessedContract, review.contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Associated contract not found")

    review.status = "rejected"
    review.resolved_at = datetime.now(timezone.utc)
    contract.status = "rejected"
    db.commit()

    return {"status": "rejected", "review_id": id, "contract_id": contract.id}
