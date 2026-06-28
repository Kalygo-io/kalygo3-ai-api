"""
Grant administration helpers (ai-api only — agent-api never mutates grants).

Thin CRUD over AccessGrant used by the per-resource sharing endpoints, plus
principal resolution (group id or grantee email → principal). Keeping this in one
place means every sharing endpoint creates grants identically and the audit view
reads a single table.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models import AccessGrant, AccessGroup, Account
from src.services import access
from src.services.access_group_roles import is_group_manager


def resolve_principal(
    db: Session,
    *,
    caller_account_id: int,
    access_group_id: int | None,
    grantee_email: str | None,
):
    """
    Resolve a sharing request to (principal_type, principal_id, label).

    Exactly one of access_group_id / grantee_email must be provided.
    - group: caller must manage the group (owner/admin).
    - individual: resolve by email; cannot grant to self.
    Raises HTTPException on validation failure.
    """
    if (access_group_id is None) == (grantee_email is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of accessGroupId or granteeEmail",
        )

    if access_group_id is not None:
        group = db.query(AccessGroup).filter(AccessGroup.id == access_group_id).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_manager(db, group, caller_account_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to share with this group",
            )
        return access.GROUP, group.id, group.name

    target = db.query(Account).filter(Account.email == grantee_email).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found for the given email")
    if target.id == caller_account_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this resource")
    return access.ACCOUNT, target.id, target.email


def upsert_grant(
    db: Session,
    *,
    principal_type: str,
    principal_id: int,
    resource_type: str,
    resource_id: int,
    role: str,
) -> AccessGrant:
    """Create the grant, or update its role if one already exists. Caller commits."""
    grant = (
        db.query(AccessGrant)
        .filter(
            AccessGrant.principal_type == principal_type,
            AccessGrant.principal_id == principal_id,
            AccessGrant.resource_type == resource_type,
            AccessGrant.resource_id == resource_id,
        )
        .first()
    )
    if grant:
        grant.role = role
    else:
        grant = AccessGrant(
            principal_type=principal_type,
            principal_id=principal_id,
            resource_type=resource_type,
            resource_id=resource_id,
            role=role,
        )
        db.add(grant)
    return grant


def list_resource_grants(db: Session, resource_type: str, resource_id: int):
    """Raw grants on a resource (owner-facing management list)."""
    return (
        db.query(AccessGrant)
        .filter(AccessGrant.resource_type == resource_type, AccessGrant.resource_id == resource_id)
        .order_by(AccessGrant.created_at.desc())
        .all()
    )


def grant_label(db: Session, grant: AccessGrant) -> str:
    """Display label for a grant: group name or grantee email."""
    if grant.principal_type == access.GROUP:
        row = db.query(AccessGroup.name).filter(AccessGroup.id == grant.principal_id).first()
        return row[0] if row else f"group #{grant.principal_id}"
    row = db.query(Account.email).filter(Account.id == grant.principal_id).first()
    return row[0] if row else f"account #{grant.principal_id}"
