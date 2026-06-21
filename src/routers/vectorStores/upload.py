"""
Upload router for Vector Stores module.
Handles file uploads to cloud storage and triggers async processing via Pub/Sub.
"""
import logging
from fastapi import APIRouter, Request, UploadFile, File, HTTPException, Form
from typing import Optional
from src.deps import jwt_dependency, db_dependency
from src.services.vector_stores_upload_service import VectorStoresUploadService
from src.services.account_gcs_service import AccountGcsCredentialMissing
from src.db.models import VectorDbIngestionLog, Account
from src.utils.errors import handle_db_error
import uuid
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload-csv")
@limiter.limit("100/minute")
async def upload_csv_file(
    file: UploadFile = File(..., description="CSV file to upload"),
    index_name: str = Form(..., description="Pinecone index name"),
    namespace: str = Form(..., description="Pinecone namespace"),
    comment: Optional[str] = Form(None, description="Optional comment for the ingestion log"),
    batch_number: Optional[str] = Form(None, description="Optional batch UUID for grouping related operations"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a CSV file to Google Cloud Storage and queue it for async processing.
    The file will be processed (chunked and uploaded to Pinecone) asynchronously via cloud function.
    
    Creates an ingestion log entry with PENDING status that will be updated when processing completes.
    """
    try:
        if not decoded_jwt:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        account_id = int(decoded_jwt['id']) if isinstance(decoded_jwt['id'], str) else decoded_jwt['id']
        
        # Validate account exists
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Validate file type
        if not file.filename or not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Only .csv files are supported"
            )
        
        # Validate index_name and namespace are provided
        if not index_name or not index_name.strip():
            raise HTTPException(
                status_code=400,
                detail="index_name is required"
            )
        
        if not namespace or not namespace.strip():
            raise HTTPException(
                status_code=400,
                detail="namespace is required"
            )
        
        # Generate batch number if not provided
        if batch_number is None:
            batch_number = str(uuid.uuid4())
        
        # Initialize upload service
        upload_service = VectorStoresUploadService()
        
        # Upload file to the account's GCS bucket and publish to Pub/Sub
        try:
            result = await upload_service.upload_file_and_publish(
                file=file,
                user_id=str(account_id),
                user_email=str(decoded_jwt.get('email', '')),
                index_name=index_name.strip(),
                namespace=namespace.strip(),
                jwt=request.cookies.get("jwt") if request else None,
                db=db,
                account_id=account_id,
                batch_number=batch_number,
                comment=comment
            )
        except AccountGcsCredentialMissing as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to upload file")
            )
        
        # Create ingestion log entry with PENDING status
        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",  # Default to pinecone, could be made configurable
                index_name=index_name.strip(),
                namespace=namespace.strip(),
                filenames=[file.filename],
                comment=comment,
                gcs_bucket=result.get("gcs_bucket"),
                gcs_file_path=result.get("gcs_file_path"),
                vectors_added=0,
                vectors_deleted=0,
                vectors_failed=0,
                batch_number=batch_number
            )

            # Set enum values directly as strings (PostgreSQL enums accept string values)
            ingestion_log.operation_type = 'INGEST'
            ingestion_log.status = 'PENDING'
            
            db.add(ingestion_log)
            db.commit()
            db.refresh(ingestion_log)
            
            result["log_id"] = str(ingestion_log.id)
            
        except Exception as e:
            logger.warning("[UPLOAD CSV] Failed to create ingestion log entry: %s: %s", type(e).__name__, e)
            # Don't fail the upload if logging fails
            db.rollback()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[UPLOAD CSV] Unexpected error")
        raise handle_db_error(e, "[UPLOAD CSV]")

@router.post("/upload-text")
@limiter.limit("100/minute")
async def upload_text_file(
    file: UploadFile = File(..., description="Text file to upload (.txt or .md)"),
    index_name: str = Form(..., description="Pinecone index name"),
    namespace: str = Form(..., description="Pinecone namespace"),
    comment: Optional[str] = Form(None, description="Optional comment for the ingestion log"),
    batch_number: Optional[str] = Form(None, description="Optional batch UUID for grouping related operations"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Upload a text file (.txt or .md) to Google Cloud Storage and queue it for async processing.
    The file will be processed (chunked and uploaded to Pinecone) asynchronously via cloud function.
    
    Creates an ingestion log entry with PENDING status that will be updated when processing completes.
    """
    try:
        if not decoded_jwt:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        account_id = int(decoded_jwt['id']) if isinstance(decoded_jwt['id'], str) else decoded_jwt['id']
        
        # Validate account exists
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Validate file type
        if not file.filename or not file.filename.endswith(('.txt', '.md')):
            raise HTTPException(
                status_code=400,
                detail="Only .txt and .md files are supported"
            )
        
        # Validate index_name and namespace are provided
        if not index_name or not index_name.strip():
            raise HTTPException(
                status_code=400,
                detail="index_name is required"
            )
        
        if not namespace or not namespace.strip():
            raise HTTPException(
                status_code=400,
                detail="namespace is required"
            )
        
        # Generate batch number if not provided
        if batch_number is None:
            batch_number = str(uuid.uuid4())
        
        # Initialize upload service
        upload_service = VectorStoresUploadService()
        
        # Upload file to the account's GCS bucket and publish to Pub/Sub
        try:
            result = await upload_service.upload_file_and_publish(
                file=file,
                user_id=str(account_id),
                user_email=str(decoded_jwt.get('email', '')),
                index_name=index_name.strip(),
                namespace=namespace.strip(),
                jwt=request.cookies.get("jwt") if request else None,
                db=db,
                account_id=account_id,
                batch_number=batch_number,
                comment=comment
            )
        except AccountGcsCredentialMissing as e:
            raise HTTPException(status_code=400, detail=str(e))
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to upload file")
            )
        
        # Create ingestion log entry with PENDING status
        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",  # Default to pinecone, could be made configurable
                index_name=index_name.strip(),
                namespace=namespace.strip(),
                filenames=[file.filename],
                comment=comment,
                gcs_bucket=result.get("gcs_bucket"),
                gcs_file_path=result.get("gcs_file_path"),
                operation_type='INGEST',  # Direct string assignment for PostgreSQL enum
                status='PENDING',  # Direct string assignment for PostgreSQL enum
                vectors_added=0,
                vectors_deleted=0,
                vectors_failed=0,
                batch_number=batch_number
            )
            
            db.add(ingestion_log)
            db.commit()
            db.refresh(ingestion_log)
            
            result["log_id"] = str(ingestion_log.id)
            
        except Exception as e:
            logger.warning("[UPLOAD TEXT] Failed to create ingestion log entry: %s: %s", type(e).__name__, e)
            # Don't fail the upload if logging fails
            db.rollback()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[UPLOAD TEXT] Unexpected error")
        raise handle_db_error(e, "[UPLOAD TEXT]")

