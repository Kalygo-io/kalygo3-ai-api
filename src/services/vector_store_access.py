"""
Knowledge-base (vector store) access control — over the unified resolver.

Access is now stored as AccessGrant rows (resource_type='vector_store',
role 'read'|'write') keyed by the VectorStore row id, and resolved by
services/access.py. These helpers keep the index-centric signatures the
vectorStores endpoints use (index_name + owner_account_id), translating to the
VectorStore id under the hood.

Permission is now explicit per grant (read vs write) rather than derived from the
member's group-management role. Every vector-store endpoint still funnels through
authorize_vector_store, which decides WHICH account's resources the request runs
against (always the owner) and whether the caller is allowed.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models import VectorStore
from src.services import access


def _vector_store_id(db: Session, owner_account_id: int, index_name: str):
    row = (
        db.query(VectorStore.id)
        .filter(
            VectorStore.owner_account_id == owner_account_id,
            VectorStore.index_name == index_name,
        )
        .first()
    )
    return row[0] if row else None


def authorize_vector_store(
    db: Session,
    caller_account_id: int,
    index_name: str,
    owner_account_id: int | None,
    *,
    require_write: bool,
) -> int:
    """Authorize access to knowledge base ``index_name`` and return its OWNER id.

    - owner_account_id None / == caller -> the caller's OWN KB: full access.
    - otherwise -> a SHARED KB: the caller must hold a grant (directly or via a
      group) on the VectorStore at read (or write, when require_write) level.

    404 if no read access, 403 if read-only but write required.
    """
    if owner_account_id is None or owner_account_id == caller_account_id:
        return caller_account_id

    vs_id = _vector_store_id(db, owner_account_id, index_name)
    if vs_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    if not access.can_access(db, caller_account_id, access.VECTOR_STORE, vs_id, required="read"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    if require_write and not access.can_access(
        db, caller_account_id, access.VECTOR_STORE, vs_id, required="write"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You have view-only access to this shared knowledge base.",
        )

    return owner_account_id


def list_shared_vector_stores(db: Session, account_id: int) -> list[dict]:
    """Knowledge bases shared with ``account_id`` (via direct or group grants).

    Returns one entry per (owner, index) the caller can reach, with ``can_write``
    True when the caller holds a write grant.
    """
    readable_ids = access.accessible_resource_ids(db, account_id, access.VECTOR_STORE, required="read")
    if not readable_ids:
        return []
    writable_ids = access.accessible_resource_ids(db, account_id, access.VECTOR_STORE, required="write")

    rows = (
        db.query(VectorStore.id, VectorStore.owner_account_id, VectorStore.index_name)
        .filter(VectorStore.id.in_(readable_ids))
        .all()
    )
    return [
        {
            "owner_account_id": owner_account_id,
            "index_name": index_name,
            "can_write": vs_id in writable_ids,
        }
        for vs_id, owner_account_id, index_name in rows
    ]
