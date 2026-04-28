import logging
from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from src.deps import jwt_dependency
from src.services.file_upload_service import FileUploadService
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-single")
@limiter.limit("100/minute")
async def upload_single_file(
    file: UploadFile = File(..., description="Single file to upload"),
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a single file to Google Cloud Storage and queue it for async processing.
    The file will be processed (chunked and uploaded to Pinecone) asynchronously.
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            return {
                "success": False,
                "error": "Only .csv files are supported"
            }
        
        # Initialize upload service
        upload_service = FileUploadService()
        namespace = "similarity_search"
        
        # Upload file to GCS and publish to Pub/Sub
        result = await upload_service.upload_file_and_publish(
            file=file,
            user_id=str(decoded_jwt.get('id')),
            user_email=str(decoded_jwt.get('email')),
            namespace=namespace,
            jwt=request.cookies.get("jwt") if request else None
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[SIMILARITY SEARCH UPLOAD] %s: %s", type(e).__name__, e)
        return {
            "success": False,
            "error": "An unexpected error occurred. Please try again.",
        }
