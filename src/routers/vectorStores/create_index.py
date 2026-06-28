"""
Create index endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from pinecone import Pinecone

from .helpers import _pinecone_key_from_credential
from .models import CreateIndexRequest, IndexResponse
from src.db.models import VectorStore
from src.db.service_name import ServiceName
from src.services.credential_access import load_credential_for_use, resolve_default_credential
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

        # Resolve the Pinecone credential to create with: an explicit pick if
        # provided (and usable by the caller), else the account default. The
        # resolved id is frozen onto the VectorStore row below so the binding is
        # explicit going forward.
        pinecone_cred = None
        if request_body.pinecone_credential_id is not None:
            pinecone_cred = load_credential_for_use(db, account_id, request_body.pinecone_credential_id)
            if not pinecone_cred:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The selected Pinecone credential was not found or is not accessible.",
                )
        if pinecone_cred is None:
            pinecone_cred = resolve_default_credential(db, account_id, ServiceName.PINECONE_API_KEY)
        api_key = _pinecone_key_from_credential(pinecone_cred)

        # Resolve the GCS credential id to bind (explicit pick, else account
        # default). Stored on the VectorStore so source files for this index are
        # written to / read from a stable bucket. Optional — may be None.
        gcs_cred = None
        if request_body.gcs_credential_id is not None:
            gcs_cred = load_credential_for_use(db, account_id, request_body.gcs_credential_id)
            if not gcs_cred:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The selected Google Cloud Storage credential was not found or is not accessible.",
                )
        if gcs_cred is None:
            gcs_cred = resolve_default_credential(db, account_id, ServiceName.GOOGLE_CLOUD_STORAGE)

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

        # Persist the knowledge-base record with its explicit credential bindings
        # (frozen so they don't drift if account defaults change later). Upsert in
        # case a row was backfilled for a same-named index previously.
        store = (
            db.query(VectorStore)
            .filter(VectorStore.owner_account_id == account_id, VectorStore.index_name == index_name)
            .first()
        )
        if store is None:
            store = VectorStore(owner_account_id=account_id, index_name=index_name)
            db.add(store)
        store.pinecone_credential_id = pinecone_cred.id if pinecone_cred else None
        store.gcs_credential_id = gcs_cred.id if gcs_cred else None
        db.commit()

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
