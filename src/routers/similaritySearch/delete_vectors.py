import logging
from fastapi import APIRouter, Request
from src.core.schemas.DeleteVectorsRequest import DeleteVectorsRequest
import os
from src.core.clients import pc
from src.deps import jwt_dependency
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.delete("/delete-vectors")
@limiter.limit("10/minute")
def delete_vectors_in_namespace(request_body: DeleteVectorsRequest, decoded_jwt: jwt_dependency, request: Request):
    """
    Delete all vectors in a specified namespace from the Pinecone index.
    """
    try:
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        namespace = "similarity_search"  # Using the namespace for similaritySearch
        
        # Get index and delete all vectors in the namespace
        index = pc.Index(index_name)
        
        # Delete all vectors in the specified namespace
        delete_response = index.delete(namespace=namespace, delete_all=True)
        
        return {
            "success": True,
            "deleted_count": delete_response.get("deleted_count", 0),
            "namespace": namespace
        }
    except Exception as e:
        logger.error("[DELETE VECTORS] %s: %s", type(e).__name__, e)
        return {
            "success": False,
            "namespace": request_body.namespace,
            "error": "An unexpected error occurred. Please try again.",
        }