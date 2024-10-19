from fastapi import APIRouter, Query as FastAPIQuery, Request
from pydantic import BaseModel
from src.deps import db_dependency, jwt_dependency

from src.core.clients import pc
import os
import requests

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

class Query(BaseModel):
    text: str

@router.post("/workouts")
@limiter.limit("10/minute")
def workouts(jwt: jwt_dependency, query: Query, request: Request):
    index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))
    
    resp = requests.post(
        url=f"{os.getenv("EMBEDDINGS_API_URL")}/huggingface/embedding",
        json={
            'input': query.text
        }
    )

    embedding = resp.json()['embedding']

    results = index.query(
        vector=embedding,
        top_k=9,
        include_values=False,
        include_metadata=True,
        namespace='workouts',
        filter={
          "created_by": {"$ne": jwt.get('id')}
        },
    )

    final_results = [{'metadata': r['metadata'], 'score': r['score']} for r in results['matches']]

    return { 
        'recommendations': final_results
    }