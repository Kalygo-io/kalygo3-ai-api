"""
List namespaces endpoint.
"""
import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from pinecone import Pinecone

from .helpers import get_pinecone_api_key
from .models import NamespaceResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/indexes/{index_name}/namespaces", response_model=List[NamespaceResponse])
@limiter.limit("30/minute")
async def list_namespaces(
    index_name: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all namespaces within a specific Pinecone index.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Get Pinecone API key
        api_key = get_pinecone_api_key(db, account_id)
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Get index
        try:
            index = pc.Index(index_name)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="An unexpected error occurred. Please try again.",
            )
        
        # Get index stats which includes namespace information
        index_stats = index.describe_index_stats()
        
        # Extract namespaces from stats
        namespaces_data = index_stats.get("namespaces", {})
        
        namespace_responses = []
        for namespace_name, namespace_info in namespaces_data.items():
            logger.info("Namespace '%s' has %d vectors", namespace_name, namespace_info.get('vector_count', 0))
            namespace_responses.append(NamespaceResponse(
                namespace=namespace_name,
                vector_count=namespace_info.get("vector_count", 0)
            ))
        
        # If no namespaces exist, return empty list (or include default namespace if applicable)
        return namespace_responses
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR LISTING NAMESPACES]")
