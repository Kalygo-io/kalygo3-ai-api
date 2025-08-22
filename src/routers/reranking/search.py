from fastapi import APIRouter, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
import os
import json
import requests
from typing import Dict, Any, List
from src.core.clients import pc
from src.deps import jwt_dependency
from src.services import fetch_embedding

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

def serialize_search_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize a search result to ensure it's JSON-compatible.
    Removes any non-serializable objects and converts to basic types.
    """
    try:
        # Extract and clean metadata
        metadata = result.get('metadata', {})
        cleaned_metadata = {}
        
        for key, value in metadata.items():
            # Convert all values to strings or basic types
            if isinstance(value, (str, int, float, bool)):
                cleaned_metadata[key] = value
            elif value is None:
                cleaned_metadata[key] = None
            else:
                # Convert complex objects to string representation
                cleaned_metadata[key] = str(value)
        
        return {
            'id': result.get('id', ''),
            'similarity_score': float(result.get('score', 0.0)),
            'metadata': cleaned_metadata
        }
    except Exception as e:
        print(f"Error serializing result: {e}")
        return {
            'id': str(result.get('id', '')),
            'similarity_score': 0.0,
            'metadata': {}
        }

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
        
        # Perform initial similarity search with a larger pool for reranking
        # We want to show top_k_for_similarity in the first stage, but rerank from a broader pool
        rerank_pool_size = max(query.top_k_for_similarity * 3, 20)  # Get 3x more candidates for reranking
        
        initial_results = index.query(
            vector=embedding,
            top_k=rerank_pool_size,  # Get a larger pool for reranking
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
                "initial_similarity_results": [],
                "reranked_results": [],
                "reranking_applied": False,
                "initial_candidates": 0,
                "final_results": 0,
                "first_stage_count": 0,
                "second_stage_count": 0
            }
        
        # Apply similarity threshold filtering
        if query.similarity_threshold > 0.0:
            filtered_matches = [
                r for r in initial_results['matches'] 
                if r['score'] >= query.similarity_threshold
            ]
        else:
            filtered_matches = initial_results['matches']
        
        # Store top_k_for_similarity results for comparison (first stage)
        initial_similarity_results = []
        for r in filtered_matches[:query.top_k_for_similarity]:
            result = {
                'id': r.get('id', ''),
                'score': float(r.get('score', 0.0)),  # This is the similarity score
                'metadata': r.get('metadata', {}),
                'similarity_score': float(r.get('score', 0.0))  # Explicitly label as similarity_score
            }
            initial_similarity_results.append(result)
        
        # Debug: Print result counts
        print(f"Debug - Initial matches: {len(filtered_matches)}")
        print(f"Debug - top_k_for_similarity: {query.top_k_for_similarity}")
        print(f"Debug - top_k_for_rerank: {query.top_k_for_rerank}")
        print(f"Debug - Rerank pool size: {rerank_pool_size}")
        print(f"Debug - Top {query.top_k_for_similarity} similarity results count: {len(initial_similarity_results)}")
        
        # Perform re-ranking using a broader pool of candidates for more dramatic reordering
        # Use more candidates for reranking to allow lower-ranked similarity results to rise to the top
        rerank_candidates = filtered_matches[:rerank_pool_size]
        print(f"Debug - Using {len(rerank_candidates)} candidates for reranking (vs {query.top_k_for_rerank} requested)")
        
        reranked_results = await perform_reranking(query.query, rerank_candidates, jwt)
        
        # Take only the top_k_for_rerank results after re-ranking (show in second stage)
        # This ensures we respect the top_k_for_rerank parameter from the request
        final_results = reranked_results[:query.top_k_for_rerank]
        print(f"Debug - Returning top {len(final_results)} reranked results (requested: {query.top_k_for_rerank})")
        
        # If we have fewer reranked results than requested, log it for debugging
        if len(final_results) < query.top_k_for_rerank:
            print(f"Debug - Warning: Only {len(final_results)} reranked results available, requested {query.top_k_for_rerank}")
        
        # Ensure reranked results are properly serialized
        serialized_final_results = []
        for result in final_results:
            serialized_result = {
                'id': result.get('id', ''),
                'metadata': result.get('metadata', {}),
                'similarity_score': float(result.get('similarity_score', 0.0)),  # Original similarity score
                'relevance_score': float(result.get('relevance_score', 0.0))  # Cohere relevance score
            }
            serialized_final_results.append(serialized_result)
        
        # Ensure reranked results are also shown in the similarity search results for better UX
        # This allows users to see where each reranked result originally ranked
        reranked_ids = {result.get('id', '') for result in serialized_final_results}
        existing_ids = {result.get('id', '') for result in initial_similarity_results}
        
        # Add any reranked results that weren't in the initial similarity results
        for result in serialized_final_results:
            if result.get('id', '') not in existing_ids:
                # Find the original similarity score for this result
                original_similarity_score = None
                for r in filtered_matches:
                    if r.get('id', '') == result.get('id', ''):
                        original_similarity_score = float(r.get('score', 0.0))
                        break
                
                if original_similarity_score is not None:
                    similarity_result = {
                        'id': result.get('id', ''),
                        'score': original_similarity_score,
                        'metadata': result.get('metadata', {}),
                        'similarity_score': original_similarity_score
                    }
                    initial_similarity_results.append(similarity_result)
                    print(f"Debug - Added reranked result {result.get('id', '')} to similarity display with score {original_similarity_score:.3f}")
        
        # Debug: Print the structure of reranked results
        print(f"Debug - Reranked results structure:")
        for i, result in enumerate(serialized_final_results[:3]):
            print(f"  Result {i}: {result}")
        
        return {
            "success": True,
            "query": query.query,
            "top_k_for_similarity": query.top_k_for_similarity,
            "top_k_for_rerank": query.top_k_for_rerank,
            "similarity_threshold": query.similarity_threshold,
            "namespace": namespace,
            "initial_similarity_results": initial_similarity_results,
            "reranked_results": serialized_final_results,
            "reranking_applied": True,
            "initial_candidates": len(filtered_matches),
            "final_results": len(serialized_final_results),
            "first_stage_count": len(initial_similarity_results),
            "second_stage_count": len(serialized_final_results)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to perform re-ranking search: {str(e)}"
        }

async def perform_reranking(query: str, candidates: list, jwt: str) -> list:
    """
    Perform re-ranking on the initial candidates using Cohere Rerank 3.5 API.
    """
    try:
        # Check if we have any candidates to rerank
        if not candidates:
            return []
        
        # Get Cohere API key
        cohere_api_key = os.getenv("COHERE_API_KEY")
        print(f"Debug - COHERE_API_KEY available: {'YES' if cohere_api_key else 'NO'}")
        if not cohere_api_key:
            print("Warning: COHERE_API_KEY not set, falling back to original results")
            return [{'metadata': c['metadata'], 'score': c['score']} for c in candidates]
        
        # Prepare documents and query for Cohere Rerank 3.5
        docs = []
        doc_metadatas = []
        similarity_scores = []
        
        for i, r in enumerate(candidates):
            content = r['metadata'].get('content', '')
            if not content.strip():
                print(f"Warning: Empty content for candidate {i}")
                content = "No content available"  # Provide fallback content
            
            docs.append(content)
            doc_metadatas.append(r['metadata'])
            similarity_scores.append(r['score'])  # Store Pinecone similarity score (original score)
        
        print(f"Prepared {len(docs)} documents for re-ranking")
        print(f"Sample document content: {docs[0][:100] if docs else 'No documents'}...")
        
        # Call Cohere Rerank 3.5 API
        cohere_url = "https://api.cohere.ai/v1/rerank"
        headers = {
            "Authorization": f"Bearer {cohere_api_key}",
            "Content-Type": "application/json"
        }
        rerank_payload = {
            "model": "rerank-v3.5",
            "query": query,
            "documents": docs,
            "top_n": len(docs)  # Rerank all documents to get full range
        }
        
        print(f"Sending to Cohere: query='{query}', {len(docs)} documents, top_n={len(docs)}")
        print(f"Cohere API key (first 10 chars): {cohere_api_key[:10]}...")
        
        cohere_response = requests.post(cohere_url, headers=headers, json=rerank_payload)
        
        if cohere_response.status_code != 200:
            print(f"Cohere Rerank API error: {cohere_response.text}")
            # Fallback to original results if API call fails
            return [{'metadata': c['metadata'], 'score': c['score']} for c in candidates]
        
        rerank_results = cohere_response.json()
        print(f"Cohere API response status: {cohere_response.status_code}")
        print(f"Cohere API response keys: {list(rerank_results.keys())}")
        print(f"Cohere API response structure: {rerank_results}")
        
        # Debug: Print the actual relevance scores from Cohere
        print(f"Cohere relevance scores:")
        for i, item in enumerate(rerank_results.get("results", [])[:5]):
            print(f"  Index {item['index']}: relevance_score = {item['relevance_score']:.3f}")
        
        # Process re-ranked results
        reranked_candidates = []
        print(f"Cohere API returned {len(rerank_results.get('results', []))} results")
        
        for item in rerank_results.get("results", []):
            idx = item["index"]
            relevance_score = item["relevance_score"]
            similarity_score = similarity_scores[idx]  # Get corresponding similarity score
            metadata = doc_metadatas[idx]
            
            print(f"Result {idx}: relevance_score={relevance_score:.3f}, similarity_score={similarity_score:.3f}")
            
            # Include all results to show the full range of reranking effects
            # This allows lower-ranked similarity results to potentially rise to the top
            reranked_candidates.append({
                'id': candidates[idx].get('id', ''),
                'metadata': metadata,
                'similarity_score': similarity_score,  # Original similarity score
                'relevance_score': relevance_score,  # New relevance score from Cohere
            })
            print(f"  Added candidate: similarity={similarity_score:.3f}, relevance={relevance_score:.3f}")
        
        print(f"After filtering: {len(reranked_candidates)} candidates")
        
        # Sort reranked candidates by relevance_score (highest first) to show re-ranking effect
        reranked_candidates.sort(key=lambda x: x['relevance_score'], reverse=True)
        print(f"Sorted reranked candidates by relevance_score (highest first)")
        
        # Debug: Print the re-ranking results
        print(f"Cohere re-ranking results for query '{query}':")
        for i, candidate in enumerate(reranked_candidates[:5]):
            print(f"  {i+1}. ID: {candidate['id']}, "
                  f"Similarity Score: {candidate['similarity_score']:.3f}, "
                  f"Relevance Score: {candidate['relevance_score']:.3f}")
        
        # Debug: Show the difference between similarity and relevance scores
        print(f"Debug - Score comparison:")
        for i, candidate in enumerate(reranked_candidates[:5]):
            similarity = candidate.get('similarity_score', 0)
            relevance = candidate.get('relevance_score', 0)
            diff = abs(similarity - relevance)
            print(f"  {i+1}. Similarity: {similarity:.3f}, Relevance: {relevance:.3f}, Diff: {diff:.3f}")
        
        return reranked_candidates
        
    except Exception as e:
        print(f"Error in Cohere re-ranking: {e}")
        # Fallback to original results if re-ranking fails
        return [{'metadata': c['metadata'], 'score': c['score']} for c in candidates]

 