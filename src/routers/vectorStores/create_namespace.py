"""
Create namespace endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from pinecone import Pinecone

from .helpers import get_pinecone_api_key
from .models import CreateNamespaceRequest, NamespaceResponse
from src.services.vector_store_access import authorize_vector_store
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/indexes/{index_name}/namespaces", status_code=status.HTTP_201_CREATED, response_model=NamespaceResponse)
@limiter.limit("10/minute")
async def create_namespace(
    index_name: str,
    request_body: CreateNamespaceRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    owner_account_id: int | None = None,
):
    """
    Create a new namespace within a specific Pinecone index.
    
    This endpoint creates the namespace by upserting a temporary dummy vector
    (which is immediately deleted) to force Pinecone to initialize the namespace.
    If the namespace already exists, it returns the existing namespace info.
    """
    try:
        logger.info("Creating namespace '%s' for index '%s'", request_body.namespace, index_name)

        caller_account_id = account_id_from_claims(jwt)
        # Resolve the knowledge base's owner (self, or the owner of a shared KB the
        # caller may write to). Ingesting/editing requires write access.
        account_id = authorize_vector_store(db, caller_account_id, index_name, owner_account_id, require_write=True)
        account = ensure_account(db, account_id)

        # Get Pinecone API key
        api_key = get_pinecone_api_key(db, account_id)
        
        # Initialize Pinecone client
        pc = Pinecone(api_key=api_key)
        
        # Verify index exists
        try:
            index = pc.Index(index_name)
            # Verify index is accessible by getting stats
            index.describe_index_stats()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="An unexpected error occurred. Please try again.",
            )
        
        # Validate namespace name (Pinecone namespace naming rules)
        namespace_name = request_body.namespace.strip()
        if not namespace_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Namespace name cannot be empty"
            )
        
        # Check if namespace already exists
        index_stats = index.describe_index_stats()
        existing_namespaces = index_stats.get("namespaces", {})
        
        if namespace_name in existing_namespaces:
            # Namespace already exists, return it
            logger.info("Namespace '%s' already exists with %d vectors", namespace_name, existing_namespaces[namespace_name].get('vector_count', 0))
            return NamespaceResponse(
                namespace=namespace_name,
                vector_count=existing_namespaces[namespace_name].get("vector_count", 0)
            )
        
        # Create the namespace by upserting a dummy vector
        # Pinecone namespaces are created automatically on first upsert
        try:
            # Get index dimension from stats
            dimension = index_stats.get("dimension")
            if not dimension:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not determine index dimension"
                )
            
            logger.info("Creating namespace '%s' in index '%s' (dimension: %d)", namespace_name, index_name, dimension)
            
            # Create a dummy vector to initialize the namespace
            # Note: Pinecone requires at least one non-zero value in dense vectors
            dummy_id = f"__init_{namespace_name}__"
            dummy_vector = [1.0] + [0.0] * (dimension - 1)  # First element is 1.0, rest are 0.0
            
            # Upsert the dummy vector to create the namespace
            logger.debug("Upserting dummy vector to initialize namespace")
            index.upsert(
                vectors=[(dummy_id, dummy_vector)],
                namespace=namespace_name
            )
            
            logger.info("Successfully created namespace '%s'", namespace_name)
            
            # Return success response
            return NamespaceResponse(
                namespace=namespace_name,
                vector_count=0
            )
        except HTTPException:
            raise
        except Exception as e:
            raise handle_db_error(e, "[CREATE NAMESPACE]")
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR CREATING NAMESPACE]")
