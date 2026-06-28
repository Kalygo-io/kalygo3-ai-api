"""
Centralized knowledge-base (vector store) access control.

A knowledge base is a free-form Pinecone index. It has no row of its own — it is
"owned" by the single account whose Pinecone API key can reach it. It can be
shared with access groups via ``VectorStoreAccessGrant``. The permission a shared
member gets is derived from their role in the granting access group:

  - any member  -> read  (view index, namespaces, files, logs)
  - admin       -> write (create namespace, ingest, delete vectors)

This mirrors the agent-sharing access rule (see ``agent_access.py``): access flows
through ``access_group_members`` rows, so the group owner is not implicitly a
member.

Every vector-store endpoint funnels through :func:`authorize_vector_store`, the
single place that decides WHICH account's Pinecone key / GCS bucket / ingestion
log the request operates against, and whether the caller is allowed. The returned
id is always the resource owner — endpoints use it everywhere they previously used
the caller's account id.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models import AccessGroupMember, VectorStoreAccessGrant
from src.services.access_group_roles import ADMIN_ROLE


def authorize_vector_store(
    db: Session,
    caller_account_id: int,
    index_name: str,
    owner_account_id: int | None,
    *,
    require_write: bool,
) -> int:
    """Authorize access to knowledge base ``index_name`` and return its OWNER id.

    - ``owner_account_id`` None or equal to the caller -> the caller's OWN
      knowledge base: full access, returns the caller (unchanged behavior).
    - Otherwise -> a SHARED knowledge base: a grant for (owner, index) must exist
      for an access group the caller is a member of. Read is allowed for any
      member; write requires the caller hold the ``admin`` role in one of those
      granted groups.

    Raises 404 if the caller has no grant to the index, 403 if they have only
    read access but need write. Returns the owner account id to operate against.
    """
    if owner_account_id is None or owner_account_id == caller_account_id:
        return caller_account_id

    # Groups granting (owner, index) that the caller is a member of.
    member_group_ids = [
        gid
        for (gid,) in (
            db.query(VectorStoreAccessGrant.access_group_id)
            .join(
                AccessGroupMember,
                AccessGroupMember.access_group_id == VectorStoreAccessGrant.access_group_id,
            )
            .filter(
                VectorStoreAccessGrant.owner_account_id == owner_account_id,
                VectorStoreAccessGrant.index_name == index_name,
                AccessGroupMember.account_id == caller_account_id,
            )
            .distinct()
            .all()
        )
    ]
    if not member_group_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")

    if require_write:
        is_admin = (
            db.query(AccessGroupMember.id)
            .filter(
                AccessGroupMember.access_group_id.in_(member_group_ids),
                AccessGroupMember.account_id == caller_account_id,
                AccessGroupMember.role == ADMIN_ROLE,
            )
            .first()
            is not None
        )
        if not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have view-only access to this shared knowledge base.",
            )

    return owner_account_id


def list_shared_vector_stores(db: Session, account_id: int) -> list[dict]:
    """Knowledge bases shared with ``account_id`` via group membership.

    Returns one entry per (owner, index) the caller can reach, with ``can_write``
    True when the caller is an admin in any granting group.
    """
    rows = (
        db.query(
            VectorStoreAccessGrant.owner_account_id,
            VectorStoreAccessGrant.index_name,
            AccessGroupMember.role,
        )
        .join(
            AccessGroupMember,
            AccessGroupMember.access_group_id == VectorStoreAccessGrant.access_group_id,
        )
        .filter(AccessGroupMember.account_id == account_id)
        .all()
    )

    can_write: dict[tuple[int, str], bool] = {}
    for owner_account_id, index_name, role in rows:
        key = (owner_account_id, index_name)
        can_write[key] = can_write.get(key, False) or (role == ADMIN_ROLE)

    return [
        {"owner_account_id": owner_account_id, "index_name": index_name, "can_write": writable}
        for (owner_account_id, index_name), writable in can_write.items()
    ]
