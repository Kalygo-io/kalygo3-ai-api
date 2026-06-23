"""
Signed-URL endpoint — returns a short-lived URL to view/download an original
document stored in the account's own GCS bucket (e.g. the source file a vector
search result points back to via storage_bucket / storage_path).

The bucket is always the account's configured bucket; only the object path is
accepted from the client, so a caller cannot read arbitrary buckets. The path
is still scoped to the requesting account's bucket.
"""
import logging

from fastapi import APIRouter, Request, Query, HTTPException, status

from src.deps import jwt_dependency, db_dependency, ensure_account
from src.services import account_gcs_service
from src.services.account_gcs_service import AccountGcsCredentialMissing
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/signed-url")
@limiter.limit("120/minute")
async def get_signed_url(
    request: Request,
    path: str = Query(..., description="Object path within the account's bucket"),
    expires: int = Query(900, ge=60, le=3600, description="URL lifetime in seconds"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
):
    """Return a short-lived signed GET URL for an object in the account's bucket."""
    try:
        if not decoded_jwt:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

        account_id = int(decoded_jwt['id']) if isinstance(decoded_jwt['id'], str) else decoded_jwt['id']

        account = ensure_account(db, account_id)

        if not path or not path.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A path is required")

        try:
            url = account_gcs_service.generate_signed_url(
                db,
                account_id,
                gcs_file_path=path,
                expiration_seconds=expires,
            )
        except AccountGcsCredentialMissing as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        return {"url": url, "expires_in": expires}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[FILES SIGNED URL] Unexpected error")
        raise handle_db_error(e, "[FILES SIGNED URL]")
