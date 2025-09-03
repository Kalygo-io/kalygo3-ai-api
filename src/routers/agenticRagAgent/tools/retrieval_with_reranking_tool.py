from langchain.tools.base import StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field

from typing import Any, Dict, List, Optional

import aiohttp
import os
import requests

from src.core.clients import pc

async def retrieval_with_reranking_impl(query: str, namespace: str = "reranking", top_k_for_similarity: int = 10, top_k_for_rerank: int = 8) -> Dict:
    """
    Perform retrieval with reranking using vector embeddings and Cohere Rerank 3.5.
    """
    try:
        # Get embedding for the query
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
        
        results = index.query(
            vector=embedding,
            top_k=rerank_pool_size,  # Get a larger pool for reranking
            include_values=False,
            include_metadata=True,
            namespace="reranking"
        )
        
        if not results['matches']:
            return {
                "message": "No relevant documents found",
                "reranked_results": [],
            }
        
        # Prepare documents for Cohere Rerank 3.5
        cohere_api_key = os.getenv("COHERE_API_KEY")
        if not cohere_api_key:
            # Fallback to similarity search only if Cohere API key is not available
            similarity_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]
            return {
                "message": "Cohere API key not available, using similarity search only",
                "reranked_results": similarity_results, # HACK IN CASE COHERE API KEY IS NOT AVAILABLE
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
        
        print(f"Prepared {len(docs)} documents for re-ranking")
        
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
        
        cohere_response = requests.post(cohere_url, headers=headers, json=rerank_payload)
        
        if cohere_response.status_code != 200:
            print(f"Cohere Rerank API error: {cohere_response.text}")
            # Fallback to original results if API call fails
            fallback_results = []
            for r in results['matches']:
                fallback_results.append({
                    'metadata': r['metadata'], 
                    'similarity_score': r['score'],
                    'relevance_score': r['score']  # Use similarity score as fallback
                })
            return {
                "message": f"Cohere API error: {cohere_response.text}, using similarity search only",
                "reranked_results": fallback_results[:top_k_for_rerank],
            }
        
        rerank_results = cohere_response.json()
        
        # Process reranked results
        reranked_matches = []
        print(f"Cohere API returned {len(rerank_results.get('results', []))} results")
        
        for item in rerank_results.get("results", []):
            idx = item["index"]
            relevance_score = item["relevance_score"]
            similarity_score = similarity_scores[idx]
            metadata = doc_metadatas[idx]
            
            # Include all results to show the full range of reranking effects
            # This allows lower-ranked similarity results to potentially rise to the top
            reranked_matches.append({
                "metadata": metadata,
                "relevance_score": relevance_score,
                "similarity_score": similarity_score
            })
        
        # Sort by relevance score (highest first) to show re-ranking effect
        reranked_matches.sort(key=lambda x: x['relevance_score'], reverse=True)
        print(f"After reranking: {len(reranked_matches)} candidates")
        
        # Prepare similarity results for comparison (show top_k_for_similarity results)
        similarity_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches'][:top_k_for_similarity]]
        
        # Take only the top_k_for_rerank results after re-ranking
        final_reranked_results = reranked_matches[:top_k_for_rerank]
        
        return {
            "message": f"Retrieved {len(final_reranked_results)} relevant documents using reranking",
            "reranked_results": final_reranked_results,
            "query": query,
            "namespace": namespace
        }
        
    except Exception as e:
        print(f"Error in retrieval with reranking: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        # Fallback to original results if re-ranking fails
        fallback_results = []
        for r in results.get('matches', [])[:top_k_for_rerank]:
            fallback_results.append({
                'metadata': r['metadata'], 
                'similarity_score': r['score'],
                'relevance_score': r['score']  # Use similarity score as fallback
            })
        return {
            "error": f"Failed to perform retrieval with reranking: {str(e)}",
            "reranked_results": fallback_results,
        }

class RetrievalQuery(BaseModel):
    query: str = Field(description="The search query to retrieve relevant documents")
    namespace: str = Field(default="agentic_rag_agent", description="The Pinecone namespace to search in")
    top_k_for_similarity: int = Field(default=10, description="Number of similarity search results to return")
    top_k_for_rerank: int = Field(default=10, description="Number of reranked results to return")

retrieval_with_reranking_tool = StructuredTool(
    name="retrieval_with_reranking",
    description="A tool for retrieving relevant documents using vector similarity search with Cohere reranking for improved relevance. Use this when you need to find specific information from the knowledge base.",
    func=retrieval_with_reranking_impl,
    coroutine=retrieval_with_reranking_impl,
    args_schema=RetrievalQuery,
)
