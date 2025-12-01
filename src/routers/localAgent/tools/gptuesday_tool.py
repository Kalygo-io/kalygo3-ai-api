from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from typing import Any, Dict, List, Optional

import aiohttp
import os

from src.core.clients import pc

async def search_the_index(query: str) -> Dict:

    embedding = {}
    async with aiohttp.ClientSession() as session:
        print("EMBEDDINGS_API_URL")
        print(os.getenv("EMBEDDINGS_API_URL"))
        url = f"{os.getenv("EMBEDDINGS_API_URL")}/huggingface/embedding"
        payload = {
            "input": query
        }
        try:

            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    # Raise an exception for non-successful status codes
                    raise aiohttp.ClientError(f"Request failed with status code {response.status}: {await response.text()}")

                result = await response.json()
                embedding = result['embedding']
        except aiohttp.ClientError as e:
            print(f"Error occurred during API request: {e}")
            return {}
        
    index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))

    results = index.query(
        vector=embedding,
        top_k=4,
        include_values=False,
        include_metadata=True,
        namespace='gptuesday'
    )

    final_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]
    
    return final_results
    

class SearchQuery(BaseModel):
    query: str = Field()
    pass

gptuesday_tool = StructuredTool(
    name="search_gptuesday_vectors",
    description="A tool for accessing info related to the GPTuesday meetup and community.",
    func=search_the_index,
    coroutine=search_the_index,
    args_schema=SearchQuery,
)