from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from app.routers.email_router import _save_pdf_attachment


def test_save_pdf_attachment_rejects_non_pdf_signature(tmp_path: Path) -> None:
    upload = UploadFile(filename="test.pdf", file=BytesIO(b"NOTPDF"))
    with pytest.raises(HTTPException) as exc:
        _save_pdf_attachment(
            attachment=upload,
            target_path=tmp_path / "contract.pdf",
            max_upload_size_bytes=1024,
        )
    assert exc.value.status_code == 400


def test_save_pdf_attachment_enforces_size_limit(tmp_path: Path) -> None:
    payload = b"%PDF-" + (b"a" * 2000)
    upload = UploadFile(filename="large.pdf", file=BytesIO(payload))
    target = tmp_path / "large.pdf"

    with pytest.raises(HTTPException) as exc:
        _save_pdf_attachment(
            attachment=upload,
            target_path=target,
            max_upload_size_bytes=1024,
        )

    assert exc.value.status_code == 413
    assert not target.exists()
