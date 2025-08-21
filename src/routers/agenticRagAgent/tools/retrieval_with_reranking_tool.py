from langchain.tools.base import StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field

from typing import Any, Dict, List, Optional

import aiohttp
import os
import requests

from src.core.clients import pc

async def retrieval_with_reranking_impl(query: str, namespace: str = "agentic_rag_agent", top_k: int = 10) -> Dict:
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
        
        # Perform initial similarity search
        results = index.query(
            vector=embedding,
            top_k=top_k,
            include_values=False,
            include_metadata=True,
            # namespace=namespace
            # namespace="chat_with_txt"
            namespace="reranking"
        )
        
        if not results['matches']:
            return {
                "message": "No relevant documents found",
                "reranked_results": [],
                "similarity_results": []
            }
        
        # Prepare documents for Cohere Rerank 3.5
        cohere_api_key = os.getenv("COHERE_API_KEY")
        if not cohere_api_key:
            # Fallback to similarity search only if Cohere API key is not available
            similarity_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]
            return {
                "message": "Cohere API key not available, using similarity search only",
                "reranked_results": similarity_results,
                "similarity_results": similarity_results
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
            "top_n": min(len(docs), 20)
        }
        
        cohere_response = requests.post(cohere_url, headers=headers, json=rerank_payload)
        
        if cohere_response.status_code != 200:
            # Fallback to similarity search if Cohere API fails
            similarity_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]
            return {
                "message": f"Cohere API error: {cohere_response.text}, using similarity search only",
                "reranked_results": similarity_results,
                "similarity_results": similarity_results
            }
        
        rerank_results = cohere_response.json()
        
        # Process reranked results
        reranked_matches = []
        for item in rerank_results.get("results", []):
            idx = item["index"]
            relevance_score = item["relevance_score"]
            similarity_score = similarity_scores[idx]
            metadata = doc_metadatas[idx]
            
            # Only keep matches with relevance score above threshold
            if relevance_score > 0.1:
                reranked_matches.append({
                    "metadata": metadata,
                    "relevance_score": relevance_score,
                    "similarity_score": similarity_score
                })
        
        # Sort by relevance score (highest first)
        reranked_matches.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Prepare similarity results for comparison
        similarity_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]
        
        return {
            "message": f"Retrieved {len(reranked_matches)} relevant documents using reranking",
            "reranked_results": reranked_matches,
            "similarity_results": similarity_results,
            "query": query,
            "namespace": namespace
        }
        
    except Exception as e:
        return {
            "error": f"Failed to perform retrieval with reranking: {str(e)}",
            "reranked_results": [],
            "similarity_results": []
        }

class RetrievalQuery(BaseModel):
    query: str = Field(description="The search query to retrieve relevant documents")
    namespace: str = Field(default="agentic_rag_agent", description="The Pinecone namespace to search in")
    top_k: int = Field(default=10, description="Number of top results to retrieve")

retrieval_with_reranking_tool = StructuredTool(
    name="retrieval_with_reranking",
    description="A tool for retrieving relevant documents using vector similarity search with Cohere reranking for improved relevance. Use this when you need to find specific information from the knowledge base.",
    func=retrieval_with_reranking_impl,
    coroutine=retrieval_with_reranking_impl,
    args_schema=RetrievalQuery,
)
