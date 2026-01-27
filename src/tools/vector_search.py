"""
Vector Search Tool

Provides semantic search over vector databases (Pinecone).
"""
from typing import Dict, Any, Optional, TypedDict, List
import os
import aiohttp
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.db.models import Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_api_key


# Type definitions for vector search results
class VectorSearchMatch(TypedDict):
    """A single match from vector search."""
    metadata: Dict[str, Any]
    score: float
    id: str


class VectorSearchSuccess(TypedDict):
    """Successful vector search result."""
    results: List[VectorSearchMatch]
    namespace: str
    index: str


class VectorSearchEmpty(TypedDict):
    """Empty vector search result."""
    results: List[VectorSearchMatch]
    message: str


class VectorSearchError(TypedDict):
    """Error result from vector search."""
    error: str


async def create_vector_search_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Session,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create a vector search tool for semantic retrieval from knowledge bases.
    
    Args:
        tool_config: Tool configuration with provider, index, namespace, etc.
        account_id: Account ID for fetching credentials
        db: Database session
        auth_token: Authentication token to pass to embedding API
        **kwargs: Additional context (unused)
        
    Returns:
        StructuredTool for vector search, or None if setup fails
        
    Example tool_config:
        {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "my-index",
            "namespace": "docs",
            "description": "Product documentation",
            "topK": 10
        }
    """
    provider = tool_config.get('provider', '').lower()
    index_name = tool_config.get('index')
    namespace = tool_config.get('namespace')
    description = tool_config.get('description', f"Search the {namespace} knowledge base")
    top_k_default = tool_config.get('topK', 10)
    
    # Validate required fields
    if not all([provider, index_name, namespace]):
        print(f"[VECTOR SEARCH TOOL] Missing required fields: provider={provider}, index={index_name}, namespace={namespace}")
        return None
    
    # Currently only support Pinecone
    if provider != 'pinecone':
        print(f"[VECTOR SEARCH TOOL] Unsupported provider: {provider}")
        return None
    
    # Get Pinecone API key from credentials
    credential = db.query(Credential).filter(
        Credential.account_id == account_id,
        Credential.service_name == ServiceName.PINECONE_API_KEY
    ).first()
    
    if not credential:
        print(f"[VECTOR SEARCH TOOL] No Pinecone API key found for account {account_id}")
        return None
    
    try:
        pinecone_api_key = decrypt_api_key(credential.encrypted_api_key)
    except Exception as e:
        print(f"[VECTOR SEARCH TOOL] Failed to decrypt Pinecone API key: {e}")
        return None
    
    # Create Pinecone client for this specific index
    from pinecone import Pinecone
    pc_client = Pinecone(api_key=pinecone_api_key)
    index = pc_client.Index(index_name)
    
    print(f"[VECTOR SEARCH TOOL] Created tool for {provider}/{index_name}/{namespace}")
    
    # Define the retrieval implementation
    async def retrieval_impl(
        query: str, 
        top_k: int = top_k_default
    ) -> VectorSearchSuccess | VectorSearchEmpty | VectorSearchError:
        """Retrieve relevant documents from the knowledge base."""
        # DEBUG: Tool invocation
        import sys
        print(f"\n{'='*60}", flush=True)
        print(f"[VECTOR SEARCH TOOL] 🚀 TOOL INVOKED: search_{namespace}", flush=True)
        print(f"[VECTOR SEARCH TOOL] 📝 Query: '{query}'", flush=True)
        print(f"[VECTOR SEARCH TOOL] 🔢 Top K: {top_k}", flush=True)
        print(f"[VECTOR SEARCH TOOL] 📦 Namespace: '{namespace}'", flush=True)
        print(f"[VECTOR SEARCH TOOL] 🗂️  Index: '{index_name}'", flush=True)
        print(f"{'='*60}\n", flush=True)
        sys.stdout.flush()
        
        try:
            # Get embedding for the query
            embedding = {}
            headers = {}
            
            # Pass authentication token (JWT or Kalygo API key) to Embeddings API
            if auth_token:
                headers["Authorization"] = f"Bearer {auth_token}"
                print(f"[VECTOR SEARCH TOOL] 🔑 Auth token present (length: {len(auth_token)})", flush=True)
            else:
                print(f"[VECTOR SEARCH TOOL] ⚠️  No auth token provided", flush=True)
            
            async with aiohttp.ClientSession() as session:
                url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"
                payload = {"input": query}
                
                print(f"[VECTOR SEARCH TOOL] 📡 Calling Embeddings API: {url}", flush=True)
                
                try:
                    async with session.post(url, json=payload, headers=headers) as response:
                        print(f"[VECTOR SEARCH TOOL] 📥 Embeddings API response status: {response.status}", flush=True)
                        
                        if response.status != 200:
                            error_text = await response.text()
                            print(f"[VECTOR SEARCH TOOL] ❌ Embeddings API error: {error_text}")
                            raise aiohttp.ClientError(f"Embedding API returned {response.status}: {error_text}")
                        
                        result = await response.json()
                        embedding = result['embedding']
                        print(f"[VECTOR SEARCH TOOL] ✅ Embedding generated (dimension: {len(embedding)})")
                except aiohttp.ClientError as e:
                    print(f"[VECTOR SEARCH TOOL] ❌ Error generating embedding: {e}")
                    return {"error": f"Failed to generate embedding: {str(e)}"}
            
            # Query Pinecone
            print(f"[VECTOR SEARCH TOOL] 🔍 Querying Pinecone...")
            print(f"[VECTOR SEARCH TOOL]   - Index: {index_name}")
            print(f"[VECTOR SEARCH TOOL]   - Namespace: {namespace}")
            print(f"[VECTOR SEARCH TOOL]   - Top K: {top_k}")
            
            results = index.query(
                vector=embedding,
                top_k=top_k,
                include_values=False,
                include_metadata=True,
                namespace=namespace
            )
            
            print(f"[VECTOR SEARCH TOOL] ✅ Pinecone query complete")
            print(f"[VECTOR SEARCH TOOL] 📊 Matches found: {len(results.get('matches', []))}")
            
            if not results['matches']:
                print(f"[VECTOR SEARCH TOOL] ⚠️  No matches found for query")
                return {"results": [], "message": "No relevant documents found"}
            
            # Format results
            formatted_results = []
            for i, match in enumerate(results['matches']):
                score = match.get('score', 0.0)
                chunk_id = match.get('id')
                print(f"[VECTOR SEARCH TOOL]   Match {i+1}: score={score:.4f}, id={chunk_id}")
                
                formatted_results.append({
                    'metadata': match.get('metadata', {}),
                    'score': score,
                    'id': chunk_id
                })
            
            print(f"[VECTOR SEARCH TOOL] 🎯 Returning {len(formatted_results)} results")
            if formatted_results:
                print(f"[VECTOR SEARCH TOOL] 📈 Score range: {formatted_results[0]['score']:.4f} - {formatted_results[-1]['score']:.4f}")
            print(f"{'='*60}\n")
            
            return {
                "results": formatted_results,
                "namespace": namespace,
                "index": index_name
            }
        except Exception as e:
            print(f"\n[VECTOR SEARCH TOOL] ❌❌❌ EXCEPTION CAUGHT ❌❌❌")
            print(f"[VECTOR SEARCH TOOL] Error: {e}")
            print(f"[VECTOR SEARCH TOOL] Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return {"error": str(e)}
    
    # Define the Pydantic schema for the tool arguments
    class SearchQuery(BaseModel):
        query: str = Field(description="The search query to find relevant documents")
        top_k: int = Field(
            default=top_k_default,
            description=f"Number of results to return (default: {top_k_default})"
        )
    
    # Create and return the StructuredTool
    return StructuredTool(
        func=retrieval_impl,
        coroutine=retrieval_impl,
        name=f"search_{namespace}",
        description=description,
        args_schema=SearchQuery
    )
