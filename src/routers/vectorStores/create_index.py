"""
Create index endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from pinecone import Pinecone

from .helpers import get_pinecone_api_key
from .models import CreateIndexRequest, IndexResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/indexes", status_code=status.HTTP_201_CREATED, response_model=IndexResponse)
@limiter.limit("10/minute")
async def create_index(
    request_body: CreateIndexRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new Pinecone index.
    
    Note: Index creation is asynchronous. The index may take some time to be ready.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Get Pinecone API key
        api_key = get_pinecone_api_key(db, account_id)
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Validate index name
        index_name = request_body.name.strip()
        if not index_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Index name cannot be empty"
            )
        
        # Validate dimension
        if request_body.dimension < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dimension must be at least 1"
            )
        
        # Validate metric
        valid_metrics = ["cosine", "euclidean", "dotproduct"]
        metric = request_body.metric.lower() if request_body.metric else "cosine"
        if metric not in valid_metrics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Metric must be one of: {', '.join(valid_metrics)}"
            )
        
        # Check if index already exists
        existing_indexes = pc.list_indexes()
        if index_name in existing_indexes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Index '{index_name}' already exists"
            )
        
        # Create the index
        try:
            pc.create_index(
                name=index_name,
                dimension=request_body.dimension,
                metric=metric,
                pods=request_body.pods,
                replicas=request_body.replicas,
                pod_type=request_body.pod_type
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An unexpected error occurred. Please try again.",
            )
        
        # Return the created index information
        return IndexResponse(
            name=index_name,
            dimension=request_body.dimension,
            metric=metric,
            pods=request_body.pods,
            replicas=request_body.replicas,
            pod_type=request_body.pod_type
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR CREATING INDEX]")
