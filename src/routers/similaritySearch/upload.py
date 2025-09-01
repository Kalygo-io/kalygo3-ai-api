from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from typing import List, Dict, Tuple, Any
from src.core.clients import pc
from src.deps import jwt_dependency
from src.services import fetch_embedding
from src.services.file_upload_service import FileUploadService

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# @router.post("/upload")
# @limiter.limit("50/minute")
# async def upload_files(
#     files: List[UploadFile] = File(..., description="Files to upload"),
#     decoded_jwt: jwt_dependency = None,
#     request: Request = None
# ):
#     """
#     Upload .txt and .md files, chunk them and upload them to a Pinecone index.
#     """
#     try:
#         if not files:
#             raise HTTPException(status_code=400, detail="No files provided")
        
#         # Get the index name from environment variables
#         index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
#         namespace = "similarity_search"  # Using the namespace for similaritySearch
        
#         # Get Pinecone index
#         index = pc.Index(index_name)
        
#         # Get JWT token for embedding service
#         jwt = request.cookies.get("jwt") if request else None
        
#         # Process each file
#         file_results = []
#         total_successful_uploads = 0
#         total_failed_uploads = 0
#         total_chunks_created = 0
        
#         for file in files:
#             print(f"Processing file: {file.filename}")
#             result = await process_single_file(file, jwt, index, namespace)
#             file_results.append(result)
            
#             if result["success"]:
#                 total_successful_uploads += result["successful_uploads"]
#                 total_failed_uploads += result["failed_uploads"]
#                 total_chunks_created += result["total_chunks_created"]
        
#         # Return format depends on whether it's single or multiple files
#         if len(files) == 1:
#             # Single file - return the result directly for backward compatibility
#             return file_results[0]
#         else:
#             # Multiple files - return aggregate results
#             return {
#                 "success": True,
#                 "files_processed": len(files),
#                 "file_results": file_results,
#                 "total_chunks_created": total_chunks_created,
#                 "total_successful_uploads": total_successful_uploads,
#                 "total_failed_uploads": total_failed_uploads,
#                 "namespace": namespace
#             }
        
#     except HTTPException:
#         raise
#     except Exception as e:
#         return {
#             "success": False,
#             "error": f"Failed to upload files: {str(e)}"
#         }

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
        if not decoded_jwt:
            raise HTTPException(status_code=401, detail="Authentication required")
        
        # Validate file type
        if not file.filename.endswith('.csv'):
            return {
                "success": False,
                "error": "Only .csv files are supported"
            }
        
        # Initialize upload service
        upload_service = FileUploadService()
        namespace = "similarity_search"
        
        print("decoded_jwt", decoded_jwt)

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
        return {
            "success": False,
            "error": f"Failed to upload file: {str(e)}"
        }
