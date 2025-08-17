from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
from src.core.clients import pc
from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.get("/kb-stats")
@limiter.limit("10/minute")
def get_knowledge_base_stats(decoded_jwt: jwt_dependency, request: Request):
    """
    Get information about the knowledge base index and namespace used by the chatWithTxt endpoint.
    """
    try:
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        namespace = "chat_with_txt"  # This is hardcoded in the generator function
        
        # Get index statistics from Pinecone
        index = pc.Index(index_name)
        index_stats = index.describe_index_stats()
        
        namespace_stats = index.describe_index_stats(filter={})
        
        return {
            "index_name": index_name,
            "namespace": namespace,
            "index_dimension": index_stats.get("dimension"),
            "index_metric": index_stats.get("metric"),
            "total_vector_count": index_stats.get("total_vector_count"),
            "namespace_vector_count": namespace_stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
        }
    except Exception as e:
        return {
            "error": f"Failed to retrieve knowledge base statistics: {str(e)}",
            "index_name": os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"),
            "namespace": "cookbook"
        } 