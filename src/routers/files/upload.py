"""
Generic per-account file upload endpoint.

Stores an uploaded file in the account's own Google Cloud Storage bucket and
returns a reference the caller can persist / forward (e.g. an Agent Chat
attachment). Uploads are blocked with HTTP 400 until the account has configured
GOOGLE_CLOUD_STORAGE credentials.
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, status

from src.deps import jwt_dependency, db_dependency
from src.db.models import Account
from src.services import account_gcs_service
from src.services.account_gcs_service import AccountGcsCredentialMissing
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Broad set of types accepted for chat attachments.
ALLOWED_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg", ".txt", ".csv", ".md")

# 25 MB cap per file.
MAX_FILE_BYTES = 25 * 1024 * 1024


@router.post("/upload")
@limiter.limit("60/minute")
async def upload_file(
    file: UploadFile = File(..., description="File to store in the account's GCS bucket"),
    session_id: Optional[str] = Form(None, description="Optional chat session id for path grouping"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
    request: Request = None,
):
    """
    Upload a file to the account's GCS bucket. Returns a GCS reference.

    Path layout: chat_uploads/{account_id}/{session_id?}/{uuid}/{filename}
    """
    try:
        if not decoded_jwt:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        account_id = int(decoded_jwt['id']) if isinstance(decoded_jwt['id'], str) else decoded_jwt['id']

        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A filename is required")

        if not file.filename.lower().endswith(ALLOWED_EXTENSIONS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        file_bytes = await file.read()
        if len(file_bytes) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty")
        if len(file_bytes) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds the {MAX_FILE_BYTES // (1024 * 1024)} MB limit",
            )

        file_id = str(uuid.uuid4())
        session_segment = f"{session_id}/" if session_id else ""
        gcs_file_path = f"chat_uploads/{account_id}/{session_segment}{file_id}/{file.filename}"

        try:
            ref = account_gcs_service.upload_bytes(
                db,
                account_id,
                file_bytes=file_bytes,
                gcs_file_path=gcs_file_path,
                content_type=file.content_type,
            )
        except AccountGcsCredentialMissing as e:
            # The single "uploads blocked until credentials configured" gate.
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        return {
            "success": True,
            "gcs_bucket": ref["gcs_bucket"],
            "gcs_file_path": ref["gcs_file_path"],
            "filename": file.filename,
            "content_type": file.content_type,
            "size": len(file_bytes),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[FILES UPLOAD] Unexpected error")
        raise handle_db_error(e, "[FILES UPLOAD]")
