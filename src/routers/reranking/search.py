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
    top_k_for_similarity: int = 5
    top_k_for_rerank: int = 10
    similarity_threshold: float = 0.0

@router.post("/search")
@limiter.limit("50/minute")
async def reranking_search(
    query: Query,
    namespace: str = "reranking",
    decoded_jwt: jwt_dependency = None,
    request: Request = None
):
    """
    Perform similarity search with re-ranking using vector embeddings.
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
        
        # Perform initial similarity search with higher top_k for re-ranking
        initial_results = index.query(
            vector=embedding,
            top_k=query.top_k_for_rerank,  # Get more results for re-ranking
            include_values=False,
            include_metadata=True,
            namespace=namespace
        )
        
        if not initial_results['matches']:
            return {
                "success": True,
                "query": query.query,
                "top_k_for_similarity": query.top_k_for_similarity,
                "top_k_for_rerank": query.top_k_for_rerank,
                "similarity_threshold": query.similarity_threshold,
                "namespace": namespace,
                "results": [],
                "reranking_applied": False
            }
        
        # Apply similarity threshold filtering
        if query.similarity_threshold > 0.0:
            filtered_matches = [
                r for r in initial_results['matches'] 
                if r['score'] >= query.similarity_threshold
            ]
        else:
            filtered_matches = initial_results['matches']
        
        # Perform re-ranking using cross-encoder or additional scoring
        reranked_results = await perform_reranking(query.query, filtered_matches, jwt)
        
        # Take only the top_k_for_similarity results after re-ranking
        final_results = reranked_results[:query.top_k_for_similarity]
        
        return {
            "success": True,
            "query": query.query,
            "top_k_for_similarity": query.top_k_for_similarity,
            "top_k_for_rerank": query.top_k_for_rerank,
            "similarity_threshold": query.similarity_threshold,
            "namespace": namespace,
            "results": final_results,
            "reranking_applied": True,
            "initial_candidates": len(filtered_matches),
            "final_results": len(final_results)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to perform re-ranking search: {str(e)}"
        }

async def perform_reranking(query: str, candidates: list, jwt: str) -> list:
    """
    Perform re-ranking on the initial candidates using cross-encoder or additional scoring.
    This is a placeholder for more sophisticated re-ranking logic.
    """
    try:
        # For now, implement a simple re-ranking based on content relevance
        # In a production system, you might use:
        # - Cross-encoder models (e.g., BERT cross-encoder)
        # - Additional scoring based on content quality
        # - User feedback integration
        # - Domain-specific ranking rules
        
        reranked_candidates = []
        
        for candidate in candidates:
            # Calculate additional relevance score based on content
            content = candidate['metadata'].get('content', '')
            question = candidate['metadata'].get('q', '')
            answer = candidate['metadata'].get('a', '')
            
            # Simple relevance scoring (can be enhanced with more sophisticated methods)
            relevance_score = calculate_content_relevance(query, question, answer)
            
            # Combine original similarity score with relevance score
            combined_score = (candidate['score'] * 0.7) + (relevance_score * 0.3)
            
            reranked_candidates.append({
                'metadata': candidate['metadata'],
                'score': candidate['score'],
                'reranked_score': combined_score,
                'relevance_score': relevance_score
            })
        
        # Sort by combined score (reranked_score)
        reranked_candidates.sort(key=lambda x: x['reranked_score'], reverse=True)
        
        return reranked_candidates
        
    except Exception as e:
        print(f"Error in re-ranking: {e}")
        # Fallback to original results if re-ranking fails
        return [{'metadata': c['metadata'], 'score': c['score']} for c in candidates]

def calculate_content_relevance(query: str, question: str, answer: str) -> float:
    """
    Calculate content relevance score between query and Q&A pair.
    This is a simple implementation that can be enhanced with more sophisticated methods.
    """
    try:
        query_lower = query.lower()
        question_lower = question.lower()
        answer_lower = answer.lower()
        
        # Simple keyword matching
        query_words = set(query_lower.split())
        question_words = set(question_lower.split())
        answer_words = set(answer_lower.split())
        
        # Calculate word overlap
        question_overlap = len(query_words.intersection(question_words)) / max(len(query_words), 1)
        answer_overlap = len(query_words.intersection(answer_words)) / max(len(query_words), 1)
        
        # Weight question more heavily than answer
        relevance_score = (question_overlap * 0.7) + (answer_overlap * 0.3)
        
        # Normalize to 0-1 range
        return min(relevance_score, 1.0)
        
    except Exception as e:
        print(f"Error calculating content relevance: {e}")
        return 0.0 