import logging
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile

from app.core.security import verify_webhook_api_key
from app.services.pipeline_executor import PipelineExecutor
from app.services.webhook_service import build_deferred_webhook_response, build_webhook_response


def _sanitize_log_value(value: str) -> str:
    return " ".join(value.splitlines()).strip()


def build_email_router(
    pipeline_executor: PipelineExecutor,
    upload_dir: Path,
    max_upload_size_bytes: int,
) -> APIRouter:
    router = APIRouter(prefix="", tags=["email"])
    logger = logging.getLogger(__name__)
    upload_dir.mkdir(parents=True, exist_ok=True)

    @router.post("/email-webhook")
    async def email_webhook(
        background_tasks: BackgroundTasks,  # preserved for compatibility
        sender: str = Form(...),
        subject: str = Form(...),
        attachment: UploadFile = File(...),
        x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
        _authorized: None = Depends(verify_webhook_api_key),
    ) -> dict:
        start = time.perf_counter()

        if not attachment.filename:
            raise HTTPException(status_code=400, detail="Missing attachment filename")

        suffix = Path(attachment.filename).suffix.lower()
        if suffix != ".pdf":
            raise HTTPException(status_code=400, detail="Only PDF attachments are supported")

        if attachment.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Invalid attachment content type")

        file_id = uuid.uuid4().hex
        target_path = upload_dir / f"{file_id}.pdf"

        _save_pdf_attachment(
            attachment=attachment,
            target_path=target_path,
            max_upload_size_bytes=max_upload_size_bytes,
        )

        logger.info(
            "Email webhook accepted",
            extra={
                "event": "email_webhook_received",
                "sender": _sanitize_log_value(sender),
                "subject": _sanitize_log_value(subject),
                "file_path": str(target_path),
                "idempotency_key_present": bool((x_idempotency_key or "").strip()),
            },
        )

        outcome = await pipeline_executor.submit_and_wait(
            sender=sender,
            subject=subject,
            file_path=str(target_path),
            idempotency_key=x_idempotency_key,
        )
        processing_time_ms = int((time.perf_counter() - start) * 1000)
        if outcome.completed and outcome.result is not None:
            response = build_webhook_response(
                result=outcome.result,
                processing_time_ms=processing_time_ms,
            )
        else:
            response = build_deferred_webhook_response(
                request_id=outcome.request_id,
                processing_time_ms=processing_time_ms,
            )

        logger.info(
            "Email webhook processed",
            extra={
                "event": "email_webhook_processed",
                "sender": _sanitize_log_value(sender),
                "subject": _sanitize_log_value(subject),
                "contract_id": response.get("contract_id"),
                "decision": response.get("decision"),
                "risk_level": response.get("risk_level"),
                "processing_time_ms": processing_time_ms,
                "status": response.get("status"),
            },
        )

        return response

    return router


def _save_pdf_attachment(
    *,
    attachment: UploadFile,
    target_path: Path,
    max_upload_size_bytes: int,
) -> None:
    file_header = attachment.file.read(5)
    attachment.file.seek(0)
    if file_header != b"%PDF-":
        raise HTTPException(status_code=400, detail="Attachment content is not a valid PDF")

    bytes_written = 0
    chunk_size = 1024 * 1024

    try:
        with target_path.open("wb") as out_file:
            while True:
                chunk = attachment.file.read(chunk_size)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_upload_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Attachment exceeds max size of {max_upload_size_bytes} bytes",
                    )
                out_file.write(chunk)
    except Exception:
        target_path.unlink(missing_ok=True)
        raise
