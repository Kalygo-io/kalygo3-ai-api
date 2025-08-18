from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import json
from src.core.clients import pc
from src.deps import jwt_dependency
from src.services import fetch_embedding

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

class Query(BaseModel):
    query: str

@router.post("/search")
@limiter.limit("50/minute")
async def similarity_search(
    query: Query,
    top_k: int = 5,
    namespace: str = "similarity_search",
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Perform similarity search using vector embeddings.
    """
    try:
        # Get JWT token for embedding service
        jwt = request.cookies.get("jwt") if request else None
        
        # Get embedding for the query
        embedding = await fetch_embedding(jwt, query.query)
        
        if embedding is None:
            return {
                "success": False,
                "error": "Failed to generate embedding for query"
            }
        
        # Get the index name from environment variables
        index_name = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
        
        # Get Pinecone index
        index = pc.Index(index_name)
        
        # Perform similarity search
        results = index.query(
            vector=embedding,
            top_k=top_k,
            include_values=False,
            include_metadata=True,
            namespace=namespace
        )
        
        final_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]

        return {
            "success": True,
            "query": query.query,
            "namespace": namespace,
            "results": final_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to perform similarity search: {str(e)}"
        } 