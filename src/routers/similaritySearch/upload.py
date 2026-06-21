import logging
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from src.deps import jwt_dependency, db_dependency
from src.services.file_upload_service import FileUploadService
from src.services.account_gcs_service import AccountGcsCredentialMissing
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-single")
@limiter.limit("100/minute")
async def upload_single_file(
    file: UploadFile = File(..., description="Single file to upload"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a single file to the account's Google Cloud Storage bucket and queue
    it for async processing (chunked and uploaded to Pinecone).
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            return {
                "success": False,
                "error": "Only .csv files are supported"
            }

        account_id = int(decoded_jwt['id']) if isinstance(decoded_jwt['id'], str) else decoded_jwt['id']

        # Initialize upload service
        upload_service = FileUploadService()
        namespace = "similarity_search"

        # Upload file to the account's GCS bucket and publish to Pub/Sub
        try:
            result = await upload_service.upload_file_and_publish(
                file=file,
                user_id=str(decoded_jwt.get('id')),
                user_email=str(decoded_jwt.get('email')),
                namespace=namespace,
                jwt=request.cookies.get("jwt") if request else None,
                db=db,
                account_id=account_id,
            )
        except AccountGcsCredentialMissing as e:
            raise HTTPException(status_code=400, detail=str(e))

        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[SIMILARITY SEARCH UPLOAD] %s: %s", type(e).__name__, e)
        return {
            "success": False,
            "error": "An unexpected error occurred. Please try again.",
        }
