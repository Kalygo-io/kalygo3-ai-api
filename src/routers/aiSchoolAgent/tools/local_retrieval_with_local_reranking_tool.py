from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from typing import Any, Dict, List, Optional

import aiohttp
import os

from src.core.clients import pc

async def local_retrieval_with_local_reranking_impl(query: str, top_k_for_similarity: int = 10, top_k_for_rerank: int = 8, namespace: str = "ai_school_kb") -> Dict:
    """
    Perform retrieval with reranking using vector embeddings and a remote reranker microservice.
    """
    try:
        print(f"INSIDE Local retrieval with local reranking: {query}")

        # Get embedding for the query (using the same embedding service as before)
        embedding = {}
        async with aiohttp.ClientSession() as session:
            url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"
            payload = {"input": query}
            
            try:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        raise aiohttp.ClientError(f"Request failed with status code {response.status}: {await response.text()}")
                    
                    result = await response.json()
                    embedding = result['embedding']
            except aiohttp.ClientError as e:
                print(f"Error occurred during API request: {e}")
                return {"error": f"Failed to generate embedding: {str(e)}"}
        
        # Get Pinecone index
        index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))
        
        # Perform initial similarity search with a larger pool for reranking
        # We want to show top_k_for_similarity results, but rerank from a broader pool
        rerank_pool_size = max(top_k_for_similarity * 3, 20)  # Get 3x more candidates for reranking
        
        print(f"Performing similarity search with a larger pool for reranking: {rerank_pool_size}")

        results = index.query(
            vector=embedding,
            top_k=rerank_pool_size,  # Get a larger pool for reranking
            include_values=False,
            include_metadata=True,
            namespace="ai_school_kb"
        )

        print(f"Results from similarity search: {results}")
        print("--------------------------------")
        
        if not results['matches']:
            print("--------------------------------")
            print(f"No relevant documents found")
            print("--------------------------------")
            return {
                "message": "No relevant documents found",
                "reranked_results": [],
            }
        
        # Gather documents for reranking
        docs = []
        doc_metadatas = []
        similarity_scores = []
        
        for r in results['matches']:
            content = r['metadata'].get('content', '')
            if not content.strip():
                content = "No content available"
            
            docs.append(content)
            doc_metadatas.append(r['metadata'])
            similarity_scores.append(r['score'])
        
        print(f"Prepared {len(docs)} documents for reranking via reranker microservice")
        
        # Call reranker microservice for reranking
        reranker_api_url = os.getenv("RERANKER_API_URL")
        if not reranker_api_url:
            print("Warning: RERANKER_API_URL not set, falling back to similarity search only")
            fallback_results = []
            for r in results['matches']:
                fallback_results.append({
                    'metadata': r['metadata'], 
                    'similarity_score': r['score'],
                    'relevance_score': r['score']  # Use similarity score as fallback
                })
            return {
                "message": "RERANKER_API_URL not configured, using similarity search only",
                "reranked_results": fallback_results[:top_k_for_rerank],
            }
        
        try:
            # Prepare payload for reranker microservice
            # Expected format: {"query": query, "documents": [doc1, doc2, ...]}
            rerank_payload = {
                "query": query,
                "documents": docs
            }
            
            # Call reranker microservice
            reranker_endpoint = f"{reranker_api_url.rstrip('/')}/huggingface/rerank"
            print(f"Calling reranker microservice at {reranker_endpoint} with {len(docs)} documents...")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    reranker_endpoint,
                    json=rerank_payload,
                    timeout=aiohttp.ClientTimeout(total=60)  # 60 second timeout for reranking
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"Reranker microservice error: HTTP {response.status} - {error_text}")
                        raise aiohttp.ClientError(f"Reranker API returned status {response.status}: {error_text}")
                    
                    rerank_result = await response.json()
            
            # Parse reranker response
            # Expected response formats:
            # 1. {"scores": [score1, score2, ...]} - array of scores in same order as documents
            # 2. {"results": [{"index": idx, "relevance_score": score}, ...]} - results with indices
            # 3. {"results": [{"index": idx, "score": score}, ...]} - alternative format
            
            relevance_scores = []
            
            if "scores" in rerank_result:
                # Format 1: Direct scores array
                relevance_scores = rerank_result["scores"]
                if len(relevance_scores) != len(docs):
                    raise ValueError(f"Number of scores ({len(relevance_scores)}) doesn't match number of documents ({len(docs)})")
            elif "results" in rerank_result:
                # Format 2 or 3: Results with indices
                results_list = rerank_result["results"]
                # Initialize scores array with zeros
                relevance_scores = [0.0] * len(docs)
                
                for item in results_list:
                    idx = item.get("index")
                    score = item.get("relevance_score") or item.get("score")
                    if idx is not None and score is not None and 0 <= idx < len(docs):
                        relevance_scores[idx] = float(score)
                    else:
                        print(f"Warning: Invalid result item: {item}")
            else:
                raise ValueError(f"Unexpected reranker response format: {list(rerank_result.keys())}")
            
            # Create reranked matches with both relevance and similarity scores
            reranked_matches = []
            for idx, relevance_score in enumerate(relevance_scores):
                similarity_score = similarity_scores[idx]
                metadata = doc_metadatas[idx]
                
                reranked_matches.append({
                    "metadata": metadata,
                    "relevance_score": float(relevance_score),
                    "similarity_score": similarity_score
                })
            
            # Sort by relevance score (highest first) to show re-ranking effect
            reranked_matches.sort(key=lambda x: x['relevance_score'], reverse=True)
            print(f"After reranking via microservice: {len(reranked_matches)} candidates")
            
            # Take only the top_k_for_rerank results after re-ranking
            final_reranked_results = reranked_matches[:top_k_for_rerank]
            
            return {
                "message": f"Retrieved {len(final_reranked_results)} relevant documents using reranker microservice",
                "reranked_results": final_reranked_results,
                "query": query,
                "namespace": namespace
            }
            
        except aiohttp.ClientError as e:
            print(f"Reranker microservice HTTP error: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            # Fallback to original results if reranking fails
            fallback_results = []
            for r in results['matches']:
                fallback_results.append({
                    'metadata': r['metadata'], 
                    'similarity_score': r['score'],
                    'relevance_score': r['score']  # Use similarity score as fallback
                })
            return {
                "message": f"Reranker microservice failed: {str(e)}, using similarity search only",
                "reranked_results": fallback_results[:top_k_for_rerank],
            }
        except Exception as e:
            print(f"Reranker microservice error: {e}")
            import traceback
            print(f"Full traceback: {traceback.format_exc()}")
            # Fallback to original results if reranking fails
            fallback_results = []
            for r in results['matches']:
                fallback_results.append({
                    'metadata': r['metadata'], 
                    'similarity_score': r['score'],
                    'relevance_score': r['score']  # Use similarity score as fallback
                })
            return {
                "message": f"Reranker microservice failed: {str(e)}, using similarity search only",
                "reranked_results": fallback_results[:top_k_for_rerank],
            }
        
    except Exception as e:
        print(f"Error in local retrieval with reranking: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        # Fallback to empty results if everything fails
        return {
            "error": f"Failed to perform local retrieval with reranking: {str(e)}",
            "reranked_results": [],
        }

class LocalRetrievalQuery(BaseModel):
    query: str = Field(description="The search query to retrieve relevant documents")
    namespace: str = Field(default="ai_school_kb", description="The Pinecone namespace to search in")
    top_k_for_similarity: int = Field(default=10, description="Number of similarity search results to return")
    top_k_for_rerank: int = Field(default=10, description="Number of reranked results to return")

local_retrieval_with_local_reranking_tool = StructuredTool(
    name="local_retrieval_with_local_reranking",
    description="A tool for retrieving relevant information in the AI School knowledge base using vector similarity search with reranking via a remote reranker microservice for improved relevance. Use this when you need to find specific information from the AI School knowledge base with reranking.",
    func=local_retrieval_with_local_reranking_impl,
    coroutine=local_retrieval_with_local_reranking_impl,
    args_schema=LocalRetrievalQuery,
)

