"""
List indexes endpoint.
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from pinecone import Pinecone

from .helpers import get_pinecone_api_key
from .models import IndexResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/indexes", response_model=List[IndexResponse])
@limiter.limit("30/minute")
async def list_indexes(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all Pinecone indexes associated with the caller's Pinecone API key.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Get Pinecone API key
        api_key = get_pinecone_api_key(db, account_id)
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # List all indexes
        indexes = pc.list_indexes()
        indexes = indexes.indexes
        
        # Get detailed information for each index
        index_responses = []
        for index in indexes:
            try:
                index_obj = pc.Index(index.name)
                index_stats = index_obj.describe_index_stats()
                
                # Get index description (may require additional API call)
                index_info = {
                    "name": index.name,
                    "dimension": index_stats.get("dimension"),
                    "metric": index_stats.get("metric"),
                    "vector_count": index_stats.get("total_vector_count"),
                }
                
                index_responses.append(IndexResponse(
                    name=index.name,
                    dimension=index_info.get("dimension"),
                    metric=index_info.get("metric"),
                ))
            except Exception as e:
                # If we can't get details, still include the index name
                index_responses.append(IndexResponse(name=index.name))
        
        return index_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR LISTING INDEXES]")
