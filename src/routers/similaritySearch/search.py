from fastapi import APIRouter, Request, HTTPException
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
    top_k: int = 5
    similarity_threshold: float = 0.0

@router.post("/search")
@limiter.limit("50/minute")
async def similarity_search(
    query: Query,
    namespace: str = "prompts",
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Perform similarity search using vector embeddings.
    """
    try:
        # Extract JWT from cookie or Authorization header
        token = None
        if request:
            token = request.cookies.get("jwt")
            if not token:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header.removeprefix("Bearer ").strip()

        # Get embedding for the query
        embedding = await fetch_embedding(token, query.query)
        
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
            top_k=query.top_k,
            include_values=False,
            include_metadata=True,
            namespace=namespace
        )
        
        # Filter results by similarity threshold if provided
        if query.similarity_threshold > 0.0:
            filtered_matches = [
                r for r in results['matches'] 
                if r['score'] >= query.similarity_threshold
            ]
        else:
            filtered_matches = results['matches']
        
        final_results = [{'metadata': r['metadata'], 'score': r['score']} for r in filtered_matches]

        return {
            "success": True,
            "query": query.query,
            "top_k": query.top_k,
            "similarity_threshold": query.similarity_threshold,
            "namespace": namespace,
            "results": final_results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to perform similarity search: {str(e)}"
        }