from fastapi import APIRouter, Request
from src.core.schemas.DeleteVectorsRequest import DeleteVectorsRequest
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from src.core.clients import pc
from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

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
        namespace = "ai_school_kb"  # Using the namespace for similaritySearch
        
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
        return {
            "success": False,
            "namespace": request_body.namespace,
            "error": f"Failed to delete vectors: {str(e)}"
        } 