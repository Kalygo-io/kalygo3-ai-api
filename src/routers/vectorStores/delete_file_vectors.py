"""
Delete all vectors that belong to a single source file within a namespace.

Pinecone has no "delete by metadata grouping" guarantee across index types, and
vector ids are content hashes (no filename prefix), so we enumerate the
namespace, collect the ids whose ``filename`` metadata matches, and delete them
by id. This works on both pod-based and serverless indexes and can also target
the "(no filename)" bucket (which a metadata filter cannot express).
"""
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status
from pinecone import Pinecone

from src.db.models import VectorDbIngestionLog
from src.deps import account_id_from_claims, db_dependency, ensure_account, jwt_dependency
from src.rate_limit import limiter
from src.utils.errors import handle_db_error
from .helpers import get_pinecone_api_key_for_index
from .list_namespace_files import SCAN_CAP, collect_ids_for_filename
from .models import DeleteFileVectorsResponse
from src.services.vector_store_access import authorize_vector_store

logger = logging.getLogger(__name__)

router = APIRouter()

# Pinecone accepts up to 1000 ids per delete call.
DELETE_BATCH = 1000


@router.delete(
    "/indexes/{index_name}/namespaces/{namespace}/file-vectors",
    response_model=DeleteFileVectorsResponse,
)
@limiter.limit("10/minute")
async def delete_file_vectors_in_namespace(
    index_name: str,
    namespace: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    filename: str = Query(..., description="Source filename whose vectors to delete"),
    owner_account_id: int | None = None,
):
    """
    Delete every vector in ``namespace`` whose source filename is ``filename``.

    Uses the caller's stored Pinecone API key and logs the operation to the
    vector DB ingestion log with ``operation_type='DELETE'`` and the filename, so
    the ingestion-log fallback can account for it without treating it as a
    whole-namespace reset.
    """
    try:
        caller_account_id = account_id_from_claims(jwt)
        # Deleting a file's vectors is a write — resolve the KB owner, require write.
        account_id = authorize_vector_store(db, caller_account_id, index_name, owner_account_id, require_write=True)
        ensure_account(db, account_id)

        api_key = get_pinecone_api_key_for_index(db, account_id, index_name)
        pc = Pinecone(api_key=api_key)

        try:
            index = pc.Index(index_name)
            stats_before = index.describe_index_stats()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="An unexpected error occurred. Please try again.",
            )

        ns_info = (stats_before.get("namespaces", {}) or {}).get(namespace)
        if ns_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Namespace '{namespace}' not found in index '{index_name}'",
            )

        total = ns_info.get("vector_count", 0)
        # Per-file delete requires a full enumeration to find the matching ids.
        # Refuse oversized namespaces rather than perform a partial delete.
        if total > SCAN_CAP:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Namespace '{namespace}' is too large ({total} vectors) to "
                    "delete by file. Delete the whole namespace instead."
                ),
            )

        ids, truncated = collect_ids_for_filename(index, namespace, filename)
        if truncated:
            # Hit the cap mid-scan: the id list is incomplete, so a delete would
            # be partial. Fail closed.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Namespace is too large to safely delete this file's vectors.",
            )

        if not ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No vectors found for file '{filename}' in namespace '{namespace}'",
            )

        logger.info(
            "Deleting %d vectors for file '%s' in index='%s' namespace='%s'",
            len(ids), filename, index_name, namespace,
        )

        for i in range(0, len(ids), DELETE_BATCH):
            index.delete(ids=ids[i:i + DELETE_BATCH], namespace=namespace)

        deleted = len(ids)
        logger.info(
            "Successfully deleted %d vectors for file '%s' in namespace='%s'",
            deleted, filename, namespace,
        )

        # ── Log to VectorDbIngestionLog ───────────────────────────────
        log_id = None
        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",
                index_name=index_name,
                namespace=namespace,
                filenames=[filename],
                comment=f"Deleted {deleted} vectors for file '{filename}' in namespace '{namespace}'",
                vectors_added=0,
                vectors_deleted=deleted,
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

        return DeleteFileVectorsResponse(
            success=True,
            index_name=index_name,
            namespace=namespace,
            filename=filename,
            vectors_deleted=deleted,
            log_id=log_id,
            message=f"Deleted {deleted} vectors for file '{filename}'",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting file vectors: %s", e)

        try:
            ingestion_log = VectorDbIngestionLog(
                account_id=account_id,
                provider="pinecone",
                index_name=index_name,
                namespace=namespace,
                filenames=[filename],
                comment=f"Failed to delete vectors for file '{filename}' in namespace '{namespace}'",
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

        raise handle_db_error(e, "[DELETE FILE VECTORS]")
