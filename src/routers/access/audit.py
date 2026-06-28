"""
Access audit endpoints.

Turns the access graph into something you can read off one screen:
- effective users of a resource (grants resolved to individual accounts), and
- for an agent, the DERIVED exposure: the indexes its vector-search tools query
  and whose source documents its users can therefore open — the implicit chain
  that has no grant row of its own.
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel

from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Agent, VectorStore, Credential
from src.services import access
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

_VECTOR_TOOL_TYPES = {"vectorSearch", "vectorSearchWithReranking"}


class EffectiveAccount(BaseModel):
    account_id: int
    email: Optional[str] = None
    role: str
    via: str  # 'owner' | 'direct' | 'group:<name>'


class DerivedExposure(BaseModel):
    """A resource reachable THROUGH the audited resource (no grant of its own)."""
    resource_type: str
    resource_id: int
    label: str
    note: str


class ResourceAuditResponse(BaseModel):
    resource_type: str
    resource_id: int
    effective_accounts: List[EffectiveAccount]
    derived_exposure: List[DerivedExposure]


class ReverseAuditItem(BaseModel):
    resource_type: str
    resource_id: int
    label: str
    role: str
    via: str


def _require_owner(db, account_id: int, resource_type: str, resource_id: int):
    """Only a resource's owner may audit who can access it."""
    owner = access._resource_owner(db, resource_type, resource_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    if owner != account_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can audit access to this resource")


@router.get("/resources/{resource_type}/{resource_id}/audit", response_model=ResourceAuditResponse)
@limiter.limit("30/minute")
async def audit_resource(
    resource_type: str,
    resource_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Who can access this resource (resolved to accounts) + derived exposure.

    For an agent, derived_exposure lists each index its vector-search tools query
    — those same effective accounts can read that index's content and open its
    source documents (via /files/source-url), even with no grant on the index.
    """
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)
        if resource_type not in (access.AGENT, access.VECTOR_STORE, access.CREDENTIAL):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown resource type")
        _require_owner(db, account_id, resource_type, resource_id)

        effective = [EffectiveAccount(**e) for e in access.effective_accounts(db, resource_type, resource_id)]

        derived: List[DerivedExposure] = []
        if resource_type == access.AGENT:
            agent = db.query(Agent).filter(Agent.id == resource_id).first()
            tools = ((agent.config or {}).get("data") or {}).get("tools") or [] if agent else []
            seen = set()
            for tool in tools:
                if isinstance(tool, dict) and tool.get("type") in _VECTOR_TOOL_TYPES:
                    idx = tool.get("index")
                    if not idx or idx in seen:
                        continue
                    seen.add(idx)
                    vs = (
                        db.query(VectorStore)
                        .filter(VectorStore.owner_account_id == agent.account_id, VectorStore.index_name == idx)
                        .first()
                    )
                    derived.append(DerivedExposure(
                        resource_type=access.VECTOR_STORE,
                        resource_id=vs.id if vs else -1,
                        label=idx,
                        note="Agent users can read this index's content and open its source documents.",
                    ))

        return ResourceAuditResponse(
            resource_type=resource_type,
            resource_id=resource_id,
            effective_accounts=effective,
            derived_exposure=derived,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[AUDIT RESOURCE]")


@router.get("/report", response_model=List[ReverseAuditItem])
@limiter.limit("30/minute")
async def my_access_report(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Reverse audit: everything the caller can reach via grants, and the path."""
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)

        items = access.resources_for_account(db, account_id)
        out: List[ReverseAuditItem] = []
        for it in items:
            label = _resource_label(db, it["resource_type"], it["resource_id"])
            out.append(ReverseAuditItem(
                resource_type=it["resource_type"],
                resource_id=it["resource_id"],
                label=label,
                role=it["role"],
                via=it["via"],
            ))
        return out
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ACCESS REPORT]")


def _resource_label(db, resource_type: str, resource_id: int) -> str:
    if resource_type == access.AGENT:
        row = db.query(Agent.name).filter(Agent.id == resource_id).first()
        return row[0] if row else f"agent #{resource_id}"
    if resource_type == access.VECTOR_STORE:
        row = db.query(VectorStore.index_name).filter(VectorStore.id == resource_id).first()
        return row[0] if row else f"vector_store #{resource_id}"
    if resource_type == access.CREDENTIAL:
        row = db.query(Credential.credential_name, Credential.credential_type).filter(Credential.id == resource_id).first()
        if row:
            return row[0] or str(row[1])
        return f"credential #{resource_id}"
    return f"{resource_type} #{resource_id}"
