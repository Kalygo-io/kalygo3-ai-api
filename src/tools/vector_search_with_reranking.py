"""
Vector Search with Re-ranking Tool

Provides semantic search over vector databases with re-ranking for improved relevance.
This tool first retrieves more candidates (topK) and then re-ranks them to return
the most relevant subset (topN).
"""
from typing import Dict, Any, Optional
import os
import aiohttp
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from src.db.models import Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import get_credential_value


async def create_vector_search_with_reranking_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Any,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create a vector search with re-ranking tool for high-quality semantic retrieval.
    
    This tool performs a two-stage retrieval:
    1. Vector similarity search (retrieves topK candidates)
    2. Re-ranking with cross-encoder (returns topN most relevant)
    
    Args:
        tool_config: Tool configuration with provider, index, namespace, etc.
        account_id: Account ID for fetching credentials
        db: Database session
        auth_token: Authentication token to pass to embedding and reranker APIs
        **kwargs: Additional context (unused)
        
    Returns:
        StructuredTool for vector search with re-ranking, or None if setup fails
        
    Example tool_config:
        {
            "type": "vectorSearchWithReranking",
            "provider": "pinecone",
            "index": "my-index",
            "namespace": "docs",
            "description": "Product documentation",
            "topK": 20,
            "topN": 5
        }
    """
    provider = tool_config.get('provider', '').lower()
    index_name = tool_config.get('index')
    namespace = tool_config.get('namespace')
    description = tool_config.get('description', f"Search and rerank the {namespace} knowledge base")
    top_k_default = tool_config.get('topK', 20)  # More candidates for reranking
    top_n_default = tool_config.get('topN', 5)   # Final reranked results
    
    # Validate required fields
    if not all([provider, index_name, namespace]):
        print(f"[VECTOR SEARCH WITH RERANKING] Missing required fields: provider={provider}, index={index_name}, namespace={namespace}")
        return None
    
    # Currently only support Pinecone
    if provider != 'pinecone':
        print(f"[VECTOR SEARCH WITH RERANKING] Unsupported provider: {provider}")
        return None
    
    # Get Pinecone API key from credentials
    credential = db.query(Credential).filter(
        Credential.account_id == account_id,
        Credential.service_name == ServiceName.PINECONE_API_KEY
    ).first()
    
    if not credential:
        print(f"[VECTOR SEARCH WITH RERANKING] No Pinecone API key found for account {account_id}")
        return None
    
    try:
        pinecone_api_key = get_credential_value(credential, "api_key")
    except Exception as e:
        print(f"[VECTOR SEARCH WITH RERANKING] Failed to decrypt Pinecone API key: {e}")
        return None
    
    # Create Pinecone client for this specific index
    from pinecone import Pinecone
    pc_client = Pinecone(api_key=pinecone_api_key)
    index = pc_client.Index(index_name)
    
    print(f"[VECTOR SEARCH WITH RERANKING] Created tool for {provider}/{index_name}/{namespace}")
    
    # Define the retrieval with re-ranking implementation
    async def retrieval_with_reranking_impl(query: str, top_k: int = top_k_default, top_n: int = top_n_default) -> Dict:
        """Retrieve and rerank relevant documents from the knowledge base."""
        # DEBUG: Tool invocation
        import sys
        print(f"\n{'='*60}", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 🚀 TOOL INVOKED: search_rerank_{namespace}", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 📝 Query: '{query}'", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 🔢 Top K (candidates): {top_k}", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 🎯 Top N (final): {top_n}", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 📦 Namespace: '{namespace}'", flush=True)
        print(f"[VECTOR SEARCH WITH RERANKING] 🗂️  Index: '{index_name}'", flush=True)
        print(f"{'='*60}\n", flush=True)
        sys.stdout.flush()
        
        try:
            # Stage 1: Get embedding for the query
            embedding = {}
            headers = {}
            
            # Pass authentication token (JWT or Kalygo API key) to Embeddings API
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
                print(f"[VECTOR SEARCH WITH RERANKING] 🔑 Auth token present (length: {len(auth_token)})", flush=True)
            else:
                print(f"[VECTOR SEARCH WITH RERANKING] ⚠️  No auth token provided", flush=True)
            
            print(f"[VECTOR SEARCH WITH RERANKING] 📡 STAGE 1: Getting embedding...", flush=True)
            
            async with aiohttp.ClientSession() as session:
                url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"
                payload = {"input": query}
                
                print(f"[VECTOR SEARCH WITH RERANKING] Calling Embeddings API: {url}")
                
                try:
                    async with session.post(url, json=payload, headers=headers) as response:
                        print(f"[VECTOR SEARCH WITH RERANKING] 📥 Embeddings API response status: {response.status}")
                        
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"[VECTOR SEARCH WITH RERANKING] ❌ Embeddings API error: {error_text}")
                            raise aiohttp.ClientError(f"Embedding API returned {response.status}: {error_text}")
                        
                        result = await response.json()
                        embedding = result['embedding']
                        print(f"[VECTOR SEARCH WITH RERANKING] ✅ Embedding generated (dimension: {len(embedding)})")
                except aiohttp.ClientError as e:
                    print(f"[VECTOR SEARCH WITH RERANKING] ❌ Error generating embedding: {e}")
                    return {"error": f"Failed to generate embedding: {str(e)}"}
            
            # Stage 2: Query Pinecone for initial candidates
            print(f"\n[VECTOR SEARCH WITH RERANKING] 🔍 STAGE 2: Querying Pinecone for candidates...")
            print(f"[VECTOR SEARCH WITH RERANKING]   - Index: {index_name}")
            print(f"[VECTOR SEARCH WITH RERANKING]   - Namespace: {namespace}")
            print(f"[VECTOR SEARCH WITH RERANKING]   - Retrieving Top K: {top_k} candidates")
            
            results = index.query(
                vector=embedding,
                top_k=top_k,  # Get more candidates for reranking
                include_values=False,
                include_metadata=True,
                namespace=namespace
            )
            
            print(f"[VECTOR SEARCH WITH RERANKING] ✅ Pinecone query complete")
            print(f"[VECTOR SEARCH WITH RERANKING] 📊 Initial candidates found: {len(results.get('matches', []))}")
            
            if not results['matches']:
                print(f"[VECTOR SEARCH WITH RERANKING] ⚠️  No candidates found")
                return {
                    "results": [],
                    "message": "No relevant documents found",
                    "namespace": namespace,
                    "index": index_name
                }
            
            # Extract documents and metadata for reranking
            docs = []
            doc_metadatas = []
            similarity_scores = []
            
            print(f"[VECTOR SEARCH WITH RERANKING] 📋 Extracting documents for reranking...")
            for i, match in enumerate(results['matches']):
                content = match.get('metadata', {}).get('content', '')
                score = match.get('score', 0.0)
                if not content.strip():
                    content = "No content available"
                
                docs.append(content)
                doc_metadatas.append(match.get('metadata', {}))
                similarity_scores.append(score)
                
                if i < 3:  # Show first 3 for debugging
                    print(f"[VECTOR SEARCH WITH RERANKING]   Candidate {i+1}: score={score:.4f}, content_length={len(content)}")
            
            print(f"[VECTOR SEARCH WITH RERANKING] ✅ Extracted {len(docs)} documents for reranking")
            
            # Stage 3: Call reranker microservice
            print(f"\n[VECTOR SEARCH WITH RERANKING] 🎯 STAGE 3: Re-ranking candidates...")
            reranker_api_url = os.getenv("RERANKER_API_URL")
            if not reranker_api_url:
                print("[VECTOR SEARCH WITH RERANKING] ⚠️  Warning: RERANKER_API_URL not set, falling back to similarity search only")
                # Return top_n results from similarity search
                fallback_results = []
                for i in range(min(top_n, len(results['matches']))):
                    match = results['matches'][i]
                    fallback_results.append({
                        'metadata': match.get('metadata', {}),
                        'score': match.get('score', 0.0),
                        'id': match.get('id')
                    })
                
                return {
                    "results": fallback_results,
                    "message": "RERANKER_API_URL not configured, using similarity search only",
                    "namespace": namespace,
                    "index": index_name,
                    "reranking_applied": False
                }
            
            try:
                # Prepare payload for reranker microservice
                rerank_payload = {
                    "query": query,
                    "documents": docs
                }
                
                # Call reranker microservice
                reranker_endpoint = f"{reranker_api_url.rstrip('/')}/huggingface/rerank"
                print(f"[VECTOR SEARCH WITH RERANKING] 📡 Calling reranker at {reranker_endpoint}")
                print(f"[VECTOR SEARCH WITH RERANKING] 📄 Sending {len(docs)} documents for reranking")
                
                # Use auth token for reranker API call
                reranker_headers = {}
                if auth_token:
                    reranker_headers["Authorization"] = f"Bearer {auth_token}"
                    print(f"[VECTOR SEARCH WITH RERANKING] 🔑 Auth token included in reranker request")
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(reranker_endpoint, json=rerank_payload, headers=reranker_headers) as response:
                        print(f"[VECTOR SEARCH WITH RERANKING] 📥 Reranker API response status: {response.status}")
                        
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"[VECTOR SEARCH WITH RERANKING] ❌ Reranker API error {response.status}: {error_text}")
                            
                            # Fallback to similarity search
                            fallback_results = []
                            for i in range(min(top_n, len(results['matches']))):
                                match = results['matches'][i]
                                fallback_results.append({
                                    'metadata': match.get('metadata', {}),
                                    'score': match.get('score', 0.0),
                                    'id': match.get('id')
                                })
                            
                            return {
                                "results": fallback_results,
                                "message": f"Reranker failed, using similarity search: {error_text}",
                                "namespace": namespace,
                                "index": index_name,
                                "reranking_applied": False
                            }
                        
                        reranker_result = await response.json()
                        print(f"[VECTOR SEARCH WITH RERANKING] ✅ Reranker API call successful")
                
                # Stage 4: Process reranked results
                print(f"\n[VECTOR SEARCH WITH RERANKING] 📊 STAGE 4: Processing reranked results...")
                # The reranker returns indices and scores
                reranked_docs = reranker_result.get('results', [])
                print(f"[VECTOR SEARCH WITH RERANKING] 📋 Reranker returned {len(reranked_docs)} ranked documents")
                
                # Build final results with reranking scores
                formatted_results = []
                for i, rerank_item in enumerate(reranked_docs[:top_n]):  # Take top_n after reranking
                    idx = rerank_item.get('index')
                    relevance_score = rerank_item.get('relevance_score', 0.0)
                    
                    if idx < len(doc_metadatas):
                        chunk_id = results['matches'][idx].get('id')
                        sim_score = similarity_scores[idx]
                        
                        print(f"[VECTOR SEARCH WITH RERANKING]   Result {i+1}: relevance={relevance_score:.4f}, similarity={sim_score:.4f}, id={chunk_id}")
                        
                        formatted_results.append({
                            'metadata': doc_metadatas[idx],
                            'score': relevance_score,  # Use reranking score
                            'similarity_score': sim_score,  # Keep original similarity score
                            'id': chunk_id
                        })
                
                print(f"[VECTOR SEARCH WITH RERANKING] 🎯 Returning {len(formatted_results)} reranked results (from {len(docs)} candidates)")
                if formatted_results:
                    print(f"[VECTOR SEARCH WITH RERANKING] 📈 Relevance range: {formatted_results[0]['score']:.4f} - {formatted_results[-1]['score']:.4f}")
                print(f"{'='*60}\n")
                
                return {
                    "results": formatted_results,
                    "namespace": namespace,
                    "index": index_name,
                    "reranking_applied": True,
                    "initial_candidates": len(docs),
                    "final_results": len(formatted_results)
                }
                
            except Exception as rerank_error:
                print(f"[VECTOR SEARCH WITH RERANKING] Reranking error: {rerank_error}")
                import traceback
                traceback.print_exc()
                
                # Fallback to similarity search
                fallback_results = []
                for i in range(min(top_n, len(results['matches']))):
                    match = results['matches'][i]
                    fallback_results.append({
                        'metadata': match.get('metadata', {}),
                        'score': match.get('score', 0.0),
                        'id': match.get('id')
                    })
                
                return {
                    "results": fallback_results,
                    "message": f"Reranking failed: {str(rerank_error)}",
                    "namespace": namespace,
                    "index": index_name,
                    "reranking_applied": False
                }
        
        except Exception as e:
            print(f"\n[VECTOR SEARCH WITH RERANKING] ❌❌❌ EXCEPTION CAUGHT ❌❌❌")
            print(f"[VECTOR SEARCH WITH RERANKING] Error: {e}")
            print(f"[VECTOR SEARCH WITH RERANKING] Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return {"error": str(e)}
    
    # Define the Pydantic schema for the tool arguments
    class SearchWithRerankQuery(BaseModel):
        query: str = Field(description="The search query to find relevant documents")
        top_k: int = Field(
            default=top_k_default,
            description=f"Number of initial candidates to retrieve (default: {top_k_default})"
        )
        top_n: int = Field(
            default=top_n_default,
            description=f"Number of final reranked results to return (default: {top_n_default})"
        )
    
    # Create and return the StructuredTool
    return StructuredTool(
        func=retrieval_with_reranking_impl,
        coroutine=retrieval_with_reranking_impl,
        name=f"search_rerank_{namespace}",
        description=description,
        args_schema=SearchWithRerankQuery
    )
