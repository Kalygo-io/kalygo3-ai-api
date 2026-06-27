"""
Pydantic models for the vectorStores router.
"""
from pydantic import BaseModel
from typing import Optional, List


# ── Index models ──────────────────────────────────────────────────────────────

class CreateIndexRequest(BaseModel):
    name: str
    dimension: int
    metric: Optional[str] = "cosine"  # cosine, euclidean, or dotproduct
    pods: Optional[int] = 1
    replicas: Optional[int] = 1
    pod_type: Optional[str] = "s1.x1"  # Default pod type


class IndexResponse(BaseModel):
    name: str
    dimension: Optional[int] = None
    metric: Optional[str] = None
    pods: Optional[int] = None
    replicas: Optional[int] = None
    pod_type: Optional[str] = None
    status: Optional[dict] = None


# ── Namespace models ──────────────────────────────────────────────────────────

class CreateNamespaceRequest(BaseModel):
    namespace: str


class NamespaceResponse(BaseModel):
    namespace: str
    vector_count: Optional[int] = None


# ── Delete vectors models ────────────────────────────────────────────────────

class DeleteVectorsRequest(BaseModel):
    namespace: str


class DeleteVectorsResponse(BaseModel):
    success: bool
    index_name: str
    namespace: str
    vectors_deleted: Optional[int] = None
    log_id: Optional[str] = None
    message: Optional[str] = None


# ── Namespace files (per-file vector counts) ─────────────────────────────────

class NamespaceFile(BaseModel):
    filename: str
    vector_count: int


class NamespaceFilesResponse(BaseModel):
    index_name: str
    namespace: str
    # Authoritative namespace total from describe_index_stats.
    total_vectors: int
    # How many vectors we actually read to build the breakdown.
    scanned_vectors: int
    # True if the namespace was larger than the scan cap (breakdown is partial
    # or sourced from the ingestion log instead of a live scan).
    truncated: bool
    # 'pinecone' (live scan) or 'ingestion_log' (approximate fallback).
    source: str
    files: List[NamespaceFile]
