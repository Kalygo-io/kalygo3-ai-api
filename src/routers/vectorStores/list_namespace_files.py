"""
List the source files in a namespace and how many vectors each contributes.

Pinecone is the source of truth: there is no "group/count by metadata" API and
vector ids are content hashes (no filename prefix), so we enumerate the
namespace's ids (``list_paginated``) and read each vector's ``filename`` metadata
(``fetch``), grouping client-side.

Robustness:
  - A cheap ``describe_index_stats`` gives the namespace total. We key an
    in-process cache on (account, index, namespace, total), so an unchanged
    namespace returns instantly and any ingest/delete (which changes the total)
    naturally invalidates the entry.
  - The live scan is bounded by SCAN_CAP. Namespaces larger than the cap (or any
    Pinecone read failure) fall back to an approximate breakdown derived from the
    Postgres ingestion log, flagged via ``source``/``truncated`` — we degrade
    rather than 500.
"""
import logging
import os
import threading
from collections import OrderedDict, defaultdict
from typing import Any, Dict, Iterable, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pinecone import Pinecone

from src.db.models import VectorDbIngestionLog
from src.deps import account_id_from_claims, db_dependency, ensure_account, jwt_dependency
from src.rate_limit import limiter
from src.utils.errors import handle_db_error
from .helpers import get_pinecone_api_key
from .models import NamespaceFile, NamespaceFilesResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Max vectors to read in a single synchronous live scan. Above this we use the
# ingestion-log fallback instead of a (slow) full scan.
SCAN_CAP = int(os.getenv("NAMESPACE_FILE_SCAN_CAP", "10000"))
# Pinecone list pages cap at 100 ids; fetch accepts up to 1000 ids per call.
LIST_PAGE = 100
FETCH_BATCH = 1000
NO_FILENAME = "(no filename)"

# Count-keyed in-process cache (see module docstring). Small and self-invalidating.
_CACHE: "OrderedDict[tuple, NamespaceFilesResponse]" = OrderedDict()
_CACHE_LOCK = threading.Lock()
_CACHE_MAX = 256


def filename_of(metadata: Optional[Dict[str, Any]]) -> str:
    """The grouping key for a vector: its source filename, or a fallback bucket."""
    if not metadata:
        return NO_FILENAME
    name = metadata.get("filename")
    return name if name else NO_FILENAME


def aggregate_filename_counts(metadatas: Iterable[Optional[Dict[str, Any]]]) -> Dict[str, int]:
    """Count vectors per filename. Pure function — unit-tested directly."""
    counts: Dict[str, int] = defaultdict(int)
    for meta in metadatas:
        counts[filename_of(meta)] += 1
    return dict(counts)


def _counts_to_files(counts: Dict[str, int]) -> list:
    """Sort by vector_count desc, then filename asc, into response models."""
    files = [NamespaceFile(filename=k, vector_count=v) for k, v in counts.items()]
    files.sort(key=lambda f: (-f.vector_count, f.filename))
    return files


def _cache_get(key: tuple) -> Optional[NamespaceFilesResponse]:
    with _CACHE_LOCK:
        if key in _CACHE:
            _CACHE.move_to_end(key)
            return _CACHE[key]
    return None


def _cache_put(key: tuple, value: NamespaceFilesResponse) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = value
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX:
            _CACHE.popitem(last=False)


def _metadatas_for_ids(index, namespace: str, ids: list) -> list:
    """Fetch the given ids and return their metadata dicts (normalizing SDK shape)."""
    fetched = index.fetch(ids=ids, namespace=namespace)
    vectors = getattr(fetched, "vectors", None)
    if vectors is None and isinstance(fetched, dict):
        vectors = fetched.get("vectors")
    vectors = vectors or {}
    metadatas = []
    for vec in vectors.values():
        meta = getattr(vec, "metadata", None)
        if meta is None and isinstance(vec, dict):
            meta = vec.get("metadata")
        metadatas.append(meta)
    return metadatas


def scan_namespace_file_counts(index, namespace: str, cap: int = SCAN_CAP):
    """
    Enumerate the namespace and count vectors per filename.

    Returns (counts, scanned, truncated). Stops once ``cap`` vectors are read.
    """
    counts: Dict[str, int] = defaultdict(int)
    scanned = 0
    truncated = False
    buffer: list = []
    token = None
    done = False

    while not done:
        page = index.list_paginated(
            namespace=namespace, limit=LIST_PAGE, pagination_token=token
        )
        page_vectors = getattr(page, "vectors", None) or []
        buffer.extend(v.id for v in page_vectors)
        token = getattr(getattr(page, "pagination", None), "next", None)
        done = not token

        # Flush in fetch-sized batches; drain the remainder on the final page.
        while len(buffer) >= FETCH_BATCH or (done and buffer):
            batch = buffer[:FETCH_BATCH]
            del buffer[:FETCH_BATCH]
            for meta in _metadatas_for_ids(index, namespace, batch):
                counts[filename_of(meta)] += 1
                scanned += 1
            if scanned >= cap:
                return counts, scanned, True

    return counts, scanned, truncated


def files_from_ingestion_log(db, account_id: int, index_name: str, namespace: str) -> Dict[str, int]:
    """
    Approximate per-file counts from the Postgres ingestion log.

    Sums ``vectors_added`` per filename for INGEST rows since the most recent
    successful whole-namespace DELETE (which resets the namespace). Used only as a
    fallback for oversized namespaces or Pinecone read failures.
    """
    base = db.query(VectorDbIngestionLog).filter(
        VectorDbIngestionLog.account_id == account_id,
        VectorDbIngestionLog.index_name == index_name,
        VectorDbIngestionLog.namespace == namespace,
    )

    last_delete = (
        base.filter(
            VectorDbIngestionLog.operation_type == "DELETE",
            VectorDbIngestionLog.status == "SUCCESS",
        )
        .order_by(VectorDbIngestionLog.created_at.desc())
        .first()
    )

    ingests = base.filter(VectorDbIngestionLog.operation_type == "INGEST")
    if last_delete is not None:
        ingests = ingests.filter(
            VectorDbIngestionLog.created_at > last_delete.created_at
        )

    counts: Dict[str, int] = defaultdict(int)
    for row in ingests.all():
        added = row.vectors_added or 0
        names = row.filenames or []
        if not names:
            continue
        if len(names) == 1:
            counts[names[0]] += added
        else:
            # Rare: a single ingest event covering multiple files. We can't split
            # exactly, so apportion evenly (this path is already approximate).
            share = added // len(names)
            for n in names:
                counts[n] += share
    return dict(counts)


@router.get(
    "/indexes/{index_name}/namespaces/{namespace}/files",
    response_model=NamespaceFilesResponse,
)
@limiter.limit("20/minute")
async def list_namespace_files(
    index_name: str,
    namespace: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """List the files in a namespace with per-file vector counts."""
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)
        api_key = get_pinecone_api_key(db, account_id)
        pc = Pinecone(api_key=api_key)

        try:
            index = pc.Index(index_name)
            stats = index.describe_index_stats()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="An unexpected error occurred. Please try again.",
            )

        ns_info = (stats.get("namespaces", {}) or {}).get(namespace)
        total = ns_info.get("vector_count", 0) if ns_info else 0

        cache_key = (account_id, index_name, namespace, total)
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached

        if total == 0:
            resp = NamespaceFilesResponse(
                index_name=index_name,
                namespace=namespace,
                total_vectors=0,
                scanned_vectors=0,
                truncated=False,
                source="pinecone",
                files=[],
            )
            _cache_put(cache_key, resp)
            return resp

        # Oversized namespace → skip the slow scan, use the approximate fallback.
        if total > SCAN_CAP:
            counts = files_from_ingestion_log(db, account_id, index_name, namespace)
            resp = NamespaceFilesResponse(
                index_name=index_name,
                namespace=namespace,
                total_vectors=total,
                scanned_vectors=0,
                truncated=True,
                source="ingestion_log",
                files=_counts_to_files(counts),
            )
            _cache_put(cache_key, resp)
            return resp

        try:
            counts, scanned, truncated = scan_namespace_file_counts(index, namespace)
            source = "pinecone"
        except Exception as scan_err:
            logger.warning(
                "[LIST NAMESPACE FILES] live scan failed, falling back to log: %s",
                scan_err,
            )
            counts = files_from_ingestion_log(db, account_id, index_name, namespace)
            scanned, truncated, source = 0, False, "ingestion_log"

        resp = NamespaceFilesResponse(
            index_name=index_name,
            namespace=namespace,
            total_vectors=total,
            scanned_vectors=scanned,
            truncated=truncated,
            source=source,
            files=_counts_to_files(counts),
        )
        _cache_put(cache_key, resp)
        return resp

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST NAMESPACE FILES]")
