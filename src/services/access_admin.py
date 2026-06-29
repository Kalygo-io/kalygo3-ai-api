"""
Grant administration helpers (ai-api only — agent-api never mutates grants).

Thin CRUD over AccessGrant used by the per-resource sharing endpoints, plus
principal resolution (group id or grantee email → principal). Keeping this in one
place means every sharing endpoint creates grants identically and the audit view
reads a single table.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.db.models import (
    AccessGrant,
    AccessGrantEvent,
    AccessGroup,
    Account,
    Agent,
    Credential,
    VectorStore,
)
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
    return principal_label(db, grant.principal_type, grant.principal_id)


def principal_label(db: Session, principal_type: str, principal_id: int) -> str:
    if principal_type == access.GROUP:
        row = db.query(AccessGroup.name).filter(AccessGroup.id == principal_id).first()
        return row[0] if row else f"group #{principal_id}"
    row = db.query(Account.email).filter(Account.id == principal_id).first()
    return row[0] if row else f"account #{principal_id}"


def resource_label(db: Session, resource_type: str, resource_id: int) -> str:
    if resource_type == access.AGENT:
        row = db.query(Agent.name).filter(Agent.id == resource_id).first()
        return row[0] if row else f"agent #{resource_id}"
    if resource_type == access.VECTOR_STORE:
        row = db.query(VectorStore.index_name).filter(VectorStore.id == resource_id).first()
        return row[0] if row else f"knowledge base #{resource_id}"
    if resource_type == access.CREDENTIAL:
        row = db.query(Credential.credential_name, Credential.credential_type).filter(Credential.id == resource_id).first()
        if row:
            return row[0] or str(row[1])
        return f"credential #{resource_id}"
    return f"{resource_type} #{resource_id}"


def record_access_event(
    db: Session,
    *,
    event_type: str,
    actor_account_id: int,
    resource_type: str,
    resource_id: int,
    principal_type: str,
    principal_id: int,
    role: str | None,
) -> AccessGrantEvent:
    """
    Append an immutable audit event for a grant create/revoke/role_change,
    snapshotting actor email + principal/resource labels. Caller commits.
    """
    actor_row = db.query(Account.email).filter(Account.id == actor_account_id).first()
    event = AccessGrantEvent(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=resource_label(db, resource_type, resource_id),
        principal_type=principal_type,
        principal_id=principal_id,
        principal_label=principal_label(db, principal_type, principal_id),
        role=role,
        actor_account_id=actor_account_id,
        actor_email=actor_row[0] if actor_row else None,
    )
    db.add(event)
    return event


def revoke_resource_grants_logged(
    db: Session, *, resource_type: str, resource_id: int, actor_account_id: int
) -> int:
    """Revoke every grant on a resource, logging a 'revoke' event for each.

    Use when a resource is deleted (the cascade cleanup) so those access changes
    still appear in the audit log. Call BEFORE deleting the resource row so its
    label snapshot resolves. Caller commits.
    """
    grants = (
        db.query(AccessGrant)
        .filter(AccessGrant.resource_type == resource_type, AccessGrant.resource_id == resource_id)
        .all()
    )
    for g in grants:
        record_access_event(
            db,
            event_type="revoke",
            actor_account_id=actor_account_id,
            resource_type=g.resource_type,
            resource_id=g.resource_id,
            principal_type=g.principal_type,
            principal_id=g.principal_id,
            role=g.role,
        )
    return access.revoke_grants_for_resource(db, resource_type, resource_id)


def revoke_principal_grants_logged(
    db: Session, *, principal_type: str, principal_id: int, actor_account_id: int
) -> int:
    """Revoke every grant held by a principal, logging a 'revoke' event for each.

    Use when a principal (e.g. an access group) is deleted. Call BEFORE deleting
    the principal so its label snapshot resolves. Caller commits.
    """
    grants = (
        db.query(AccessGrant)
        .filter(AccessGrant.principal_type == principal_type, AccessGrant.principal_id == principal_id)
        .all()
    )
    for g in grants:
        record_access_event(
            db,
            event_type="revoke",
            actor_account_id=actor_account_id,
            resource_type=g.resource_type,
            resource_id=g.resource_id,
            principal_type=g.principal_type,
            principal_id=g.principal_id,
            role=g.role,
        )
    return access.revoke_grants_for_principal(db, principal_type, principal_id)
