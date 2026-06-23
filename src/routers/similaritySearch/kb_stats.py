import logging
from fastapi import APIRouter, Request
import os
from src.core.clients import pc
from src.deps import jwt_dependency
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/kb-stats")
@limiter.limit("50/minute")
def get_knowledge_base_stats(decoded_jwt: jwt_dependency, request: Request):
    """
    Get information about the knowledge base index and namespace used by the similaritySearch endpoint.
    """
    try:
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        namespace = "similarity_search"  # This is the namespace for similarity search
        
        # Get index statistics from Pinecone (includes the per-namespace map)
        index = pc.Index(index_name)
        index_stats = index.describe_index_stats()

        return {
            "index_name": index_name,
            "namespace": namespace,
            "index_dimension": index_stats.get("dimension"),
            "index_metric": index_stats.get("metric"),
            "total_vector_count": index_stats.get("total_vector_count"),
            "namespace_vector_count": index_stats.get("namespaces", {}).get(namespace, {}).get("vector_count", 0)
        }
    except Exception as e:
        logger.error("[KB STATS] %s: %s", type(e).__name__, e)
        return {
            "error": "An unexpected error occurred. Please try again.",
            "index_name": os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"),
            "namespace": "similarity_search",
        }