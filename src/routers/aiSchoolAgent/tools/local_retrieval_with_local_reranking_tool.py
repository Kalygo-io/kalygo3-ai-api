from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from typing import Any, Dict, List, Optional

import aiohttp
import os

from FlagEmbedding import FlagReranker

from src.core.clients import pc

# Initialize the reranker model (lazy loading - will be initialized on first use)
_reranker = None

def get_reranker():
    """Get or initialize the FlagReranker instance."""
    global _reranker
    if _reranker is None:
        # Use BAAI/bge-reranker-v2-m3 model (multilingual, lightweight cross-encoder)
        # use_fp16=True speeds up computation with slight performance degradation
        _reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
    return _reranker

async def local_retrieval_with_local_reranking_impl(query: str, top_k_for_similarity: int = 10, top_k_for_rerank: int = 8, namespace: str = "ai_school_kb") -> Dict:
    """
    Perform retrieval with reranking using vector embeddings and local BGE reranker (bge-reranker-v2-m3) via FlagEmbedding.
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
        
        print(f"Prepared {len(docs)} documents for local re-ranking with BGE reranker")
        
        # Use FlagReranker for reranking
        # BGE reranker is a cross-encoder that takes query-document pairs and outputs relevance scores
        try:
            reranker = get_reranker()
            
            # Create query-document pairs for reranking
            # Format: [[query, doc1], [query, doc2], ...]
            query_doc_pairs = [[query, doc] for doc in docs]
            
            # Compute relevance scores using the reranker
            # Scores can be negative or positive, higher is better
            print(f"Computing relevance scores for {len(query_doc_pairs)} query-document pairs...")
            relevance_scores = reranker.compute_score(query_doc_pairs)
            
            # Convert to list if it's a numpy array
            if hasattr(relevance_scores, 'tolist'):
                relevance_scores = relevance_scores.tolist()
            elif not isinstance(relevance_scores, list):
                relevance_scores = list(relevance_scores)
            
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
            print(f"After local reranking: {len(reranked_matches)} candidates")
            
            # Take only the top_k_for_rerank results after re-ranking
            final_reranked_results = reranked_matches[:top_k_for_rerank]
            
            return {
                "message": f"Retrieved {len(final_reranked_results)} relevant documents using local BGE reranking",
                "reranked_results": final_reranked_results,
                "query": query,
                "namespace": namespace
            }
            
        except Exception as e:
            print(f"BGE reranking error: {e}")
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
                "message": f"BGE reranking failed: {str(e)}, using similarity search only",
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
    description="A tool for retrieving relevant information in the AI School knowledge base using vector similarity search with local BGE reranking (bge-reranker-v2-m3 via FlagEmbedding) for improved relevance. Use this when you need to find specific information from the AI School knowledge base with local reranking.",
    func=local_retrieval_with_local_reranking_impl,
    coroutine=local_retrieval_with_local_reranking_impl,
    args_schema=LocalRetrievalQuery,
)

