"""
Delete vectors endpoint.
"""
import logging

from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import VectorDbIngestionLog
from pinecone import Pinecone

from .helpers import get_pinecone_api_key
from .models import DeleteVectorsResponse
from src.services.vector_store_access import authorize_vector_store
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.delete("/indexes/{index_name}/namespaces/{namespace}/vectors", response_model=DeleteVectorsResponse)
@limiter.limit("10/minute")
async def delete_vectors_in_namespace(
    index_name: str,
    namespace: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    owner_account_id: int | None = None,
):
    """
    Delete **all** vectors in a specific namespace of a Pinecone index.

    Uses the caller's stored Pinecone API key and logs the operation to the
    vector DB ingestion log with ``operation_type='DELETE'``.
    """
    try:
        caller_account_id = account_id_from_claims(jwt)
        # Deleting vectors is a write — resolve the KB owner and require write access.
        account_id = authorize_vector_store(db, caller_account_id, index_name, owner_account_id, require_write=True)
        account = ensure_account(db, account_id)

        # Get Pinecone API key for this account
        api_key = get_pinecone_api_key(db, account_id)

        # Initialise Pinecone client and connect to the index
        pc = Pinecone(api_key=api_key)

        try:
            index = pc.Index(index_name)
            # Quick sanity check that the index is reachable
            stats_before = index.describe_index_stats()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="An unexpected error occurred. Please try again.",
            )

        # Check the namespace exists and get a pre-delete vector count
        namespaces_data = stats_before.get("namespaces", {})
        ns_info = namespaces_data.get(namespace)
        if ns_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Namespace '{namespace}' not found in index '{index_name}'",
            )

        vectors_before = ns_info.get("vector_count", 0)
        logger.info("Deleting all vectors in index='%s' namespace='%s' (vector_count=%d)", index_name, namespace, vectors_before)

        # ── Perform the delete ────────────────────────────────────────
        index.delete(namespace=namespace, delete_all=True)

        logger.info("Successfully deleted vectors in index='%s' namespace='%s'", index_name, namespace)

        # ── Log to VectorDbIngestionLog ───────────────────────────────
        log_id = None
        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",
                index_name=index_name,
                namespace=namespace,
                filenames=None,
                comment=f"Deleted all vectors in namespace '{namespace}'",
                vectors_added=0,
                vectors_deleted=vectors_before,
                vectors_failed=0,
            )
            ingestion_log.operation_type = "DELETE"
            ingestion_log.status = "SUCCESS"

            db.add(ingestion_log)
            db.commit()
            db.refresh(ingestion_log)
            log_id = str(ingestion_log.id)
        except Exception as log_err:
            logger.warning("Failed to create ingestion log: %s", log_err)
            db.rollback()

        return DeleteVectorsResponse(
            success=True,
            index_name=index_name,
            namespace=namespace,
            vectors_deleted=vectors_before,
            log_id=log_id,
            message=f"Deleted all {vectors_before} vectors in namespace '{namespace}'",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting vectors: %s", e)

        # Attempt to log the failed operation
        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",
                index_name=index_name,
                namespace=namespace,
                filenames=None,
                comment=f"Failed to delete vectors in namespace '{namespace}'",
                vectors_added=0,
                vectors_deleted=0,
                vectors_failed=0,
                error_message=str(e),
            )
            ingestion_log.operation_type = "DELETE"
            ingestion_log.status = "FAILED"

            db.add(ingestion_log)
            db.commit()
        except Exception:
            db.rollback()

        raise handle_db_error(e, "[DELETE VECTORS]")
