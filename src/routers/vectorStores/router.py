"""
Vector Stores router for managing Pinecone indexes and namespaces.
All endpoints use the Pinecone API key associated with the authenticated caller.
"""
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional, List
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_api_key
from pinecone import Pinecone
from slowapi import Limiter
from slowapi.util import get_remote_address

# Import ingestion logs router
from .ingestion_logs import router as ingestion_logs_router
# Import upload router
from .upload import router as upload_router

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Include ingestion logs router
router.include_router(ingestion_logs_router)
# Include upload router
router.include_router(upload_router)

class CreateIndexRequest(BaseModel):
    name: str
    dimension: int
    metric: Optional[str] = "cosine"  # cosine, euclidean, or dotproduct
    pods: Optional[int] = 1
    replicas: Optional[int] = 1
    pod_type: Optional[str] = "s1.x1"  # Default pod type


class CreateNamespaceRequest(BaseModel):
    namespace: str


class IndexResponse(BaseModel):
    name: str
    dimension: Optional[int] = None
    metric: Optional[str] = None
    pods: Optional[int] = None
    replicas: Optional[int] = None
    pod_type: Optional[str] = None
    status: Optional[dict] = None


class NamespaceResponse(BaseModel):
    namespace: str
    vector_count: Optional[int] = None


def get_pinecone_api_key(db, account_id: int) -> str:
    """
    Helper function to retrieve and decrypt the Pinecone API key for a given account.
    
    Args:
        db: Database session
        account_id: Account ID
        
    Returns:
        Decrypted Pinecone API key
        
    Raises:
        HTTPException: If credential not found
    """
    credential = db.query(Credential).filter(
        Credential.account_id == account_id,
        Credential.service_name == ServiceName.PINECONE_API_KEY
    ).first()
    
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pinecone API key not found. Please add your Pinecone API key in credentials."
        )
    
    try:
        api_key = decrypt_api_key(credential.encrypted_api_key)
        return api_key
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to decrypt Pinecone API key: {str(e)}"
        )


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
        print(f"Error listing indexes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing indexes: {str(e)}"
        )


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
                detail=f"Index '{index_name}' not found: {str(e)}"
            )
        
        # Get index stats which includes namespace information
        index_stats = index.describe_index_stats()
        
        # Extract namespaces from stats
        namespaces_data = index_stats.get("namespaces", {})
        
        namespace_responses = []
        for namespace_name, namespace_info in namespaces_data.items():
            namespace_responses.append(NamespaceResponse(
                namespace=namespace_name,
                vector_count=namespace_info.get("vector_count", 0)
            ))
        
        # If no namespaces exist, return empty list (or include default namespace if applicable)
        return namespace_responses
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing namespaces: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing namespaces: {str(e)}"
        )


@router.post("/indexes/{index_name}/namespaces", status_code=status.HTTP_201_CREATED, response_model=NamespaceResponse)
@limiter.limit("10/minute")
async def create_namespace(
    index_name: str,
    request_body: CreateNamespaceRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new namespace within a specific Pinecone index.
    
    Note: Namespaces in Pinecone are created automatically when you first upsert data to them.
    This endpoint validates that the namespace can be used and verifies the index exists.
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
        
        # Verify index exists
        try:
            index = pc.Index(index_name)
            # Verify index is accessible by getting stats
            index.describe_index_stats()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index '{index_name}' not found or not accessible: {str(e)}"
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
            return NamespaceResponse(
                namespace=namespace_name,
                vector_count=existing_namespaces[namespace_name].get("vector_count", 0)
            )
        
        # Namespace will be created automatically on first upsert
        # Return success response indicating namespace is ready to use
        return NamespaceResponse(
            namespace=namespace_name,
            vector_count=0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating namespace: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating namespace: {str(e)}"
        )


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
                detail=f"Failed to create index: {str(e)}"
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
        print(f"Error creating index: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating index: {str(e)}"
        )


