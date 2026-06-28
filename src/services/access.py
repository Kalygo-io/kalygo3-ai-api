"""
Unified access control + audit resolution.

Single source of truth for "can this account access this resource (at this role)?"
and "who can access this resource / what can this account reach?" — across agents,
vector stores (knowledge bases), and credentials. Replaces the per-resource
modules (agent_access / vector_store_access / credential_access): every grant is an
AccessGrant row (principal × resource × role), and the account-vs-group distinction
lives only in members_of().

CANONICAL FILE. Mirrored byte-for-byte into kalygo3-agent-api
(src/services/access.py) via the repo-root sync scripts. Edit the ai-api copy,
then run ./sync-schemas.sh. Do not edit the two copies independently.

Roles: 'read' < 'write' (vector stores); 'use' (agents, credentials). The resource
OWNER implicitly satisfies any required role.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.db.models import (
    AccessGrant,
    AccessGroupMember,
    Account,
    AccessGroup,
    Agent,
    Credential,
    VectorStore,
)

# Resource type constants
AGENT = "agent"
VECTOR_STORE = "vector_store"
CREDENTIAL = "credential"

# Principal type constants
ACCOUNT = "account"
GROUP = "group"

# Role ranking for read/write resources. 'use' is matched exactly.
_ROLE_RANK = {"read": 1, "write": 2}


def role_satisfies(grant_role: str, required: str) -> bool:
    """True if a grant's role meets the required role."""
    if required == "use":
        return grant_role == "use"
    return _ROLE_RANK.get(grant_role, 0) >= _ROLE_RANK.get(required, 0)


def members_of(db: Session, principal_type: str, principal_id: int) -> set:
    """Expand a principal to the set of account ids it represents.

    The ONLY place the account-vs-group distinction is resolved.
    """
    if principal_type == ACCOUNT:
        return {principal_id}
    if principal_type == GROUP:
        rows = (
            db.query(AccessGroupMember.account_id)
            .filter(AccessGroupMember.access_group_id == principal_id)
            .all()
        )
        return {r[0] for r in rows}
    return set()


def _resource_owner(db: Session, resource_type: str, resource_id: int):
    """Return the owning account id of a resource, or None if it doesn't exist."""
    if resource_type == AGENT:
        row = db.query(Agent.account_id).filter(Agent.id == resource_id).first()
    elif resource_type == CREDENTIAL:
        row = db.query(Credential.account_id).filter(Credential.id == resource_id).first()
    elif resource_type == VECTOR_STORE:
        row = db.query(VectorStore.owner_account_id).filter(VectorStore.id == resource_id).first()
    else:
        return None
    return row[0] if row else None


def can_access(
    db: Session,
    account_id: int,
    resource_type: str,
    resource_id: int,
    required: str = "read",
) -> bool:
    """True if *account_id* can access the resource at >= *required* role.

    Owner short-circuit, then a single indexed query over grants to the account
    directly OR to a group it belongs to, filtered to roles that satisfy required.
    """
    owner = _resource_owner(db, resource_type, resource_id)
    if owner is None:
        return False
    if owner == account_id:
        return True

    grants = (
        db.query(AccessGrant.principal_type, AccessGrant.principal_id, AccessGrant.role)
        .filter(
            AccessGrant.resource_type == resource_type,
            AccessGrant.resource_id == resource_id,
        )
        .all()
    )
    if not grants:
        return False

    # Group ids the account belongs to (computed once, only if needed).
    group_ids = None
    for principal_type, principal_id, role in grants:
        if not role_satisfies(role, required):
            continue
        if principal_type == ACCOUNT and principal_id == account_id:
            return True
        if principal_type == GROUP:
            if group_ids is None:
                group_ids = {
                    r[0]
                    for r in db.query(AccessGroupMember.access_group_id)
                    .filter(AccessGroupMember.account_id == account_id)
                    .all()
                }
            if principal_id in group_ids:
                return True
    return False


def accessible_resource_ids(
    db: Session,
    account_id: int,
    resource_type: str,
    required: str = "read",
) -> set:
    """Resource ids of *resource_type* the account can reach via grants at >=
    *required* role (EXCLUDES owned — callers union owned separately).
    """
    group_ids = {
        r[0]
        for r in db.query(AccessGroupMember.access_group_id)
        .filter(AccessGroupMember.account_id == account_id)
        .all()
    }
    grants = (
        db.query(AccessGrant.resource_id, AccessGrant.role, AccessGrant.principal_type, AccessGrant.principal_id)
        .filter(AccessGrant.resource_type == resource_type)
        .all()
    )
    out = set()
    for resource_id, role, principal_type, principal_id in grants:
        if not role_satisfies(role, required):
            continue
        if (principal_type == ACCOUNT and principal_id == account_id) or (
            principal_type == GROUP and principal_id in group_ids
        ):
            out.add(resource_id)
    return out


# ── Mutation helpers (app-level cascade, since grants use polymorphic columns) ──

def revoke_grants_for_resource(db: Session, resource_type: str, resource_id: int) -> int:
    """Delete all grants on a resource (call when the resource is deleted)."""
    n = (
        db.query(AccessGrant)
        .filter(AccessGrant.resource_type == resource_type, AccessGrant.resource_id == resource_id)
        .delete(synchronize_session=False)
    )
    return n


def revoke_grants_for_principal(db: Session, principal_type: str, principal_id: int) -> int:
    """Delete all grants held by a principal (call when an account/group is deleted)."""
    n = (
        db.query(AccessGrant)
        .filter(AccessGrant.principal_type == principal_type, AccessGrant.principal_id == principal_id)
        .delete(synchronize_session=False)
    )
    return n


# ── Audit ──────────────────────────────────────────────────────────────────────

def effective_accounts(db: Session, resource_type: str, resource_id: int) -> list:
    """
    Resolve a resource's access to individual accounts, for audit.

    Returns a list of dicts: {account_id, email, role, via} where via is
    'owner' | 'direct' | 'group:<name>'. When an account is reachable by multiple
    paths the highest role wins (and 'owner' supersedes all).
    """
    owner = _resource_owner(db, resource_type, resource_id)
    best: dict = {}  # account_id -> {role, via}

    def _consider(acct_id, role, via):
        cur = best.get(acct_id)
        if cur is None or _role_priority(role) > _role_priority(cur["role"]):
            best[acct_id] = {"role": role, "via": via}

    if owner is not None:
        _consider(owner, "owner", "owner")

    grants = (
        db.query(AccessGrant.principal_type, AccessGrant.principal_id, AccessGrant.role)
        .filter(
            AccessGrant.resource_type == resource_type,
            AccessGrant.resource_id == resource_id,
        )
        .all()
    )
    # Pre-fetch group names for labeling.
    group_names = {
        gid: name
        for gid, name in db.query(AccessGroup.id, AccessGroup.name).all()
    }
    for principal_type, principal_id, role in grants:
        if principal_type == ACCOUNT:
            _consider(principal_id, role, "direct")
        elif principal_type == GROUP:
            via = f"group:{group_names.get(principal_id, principal_id)}"
            for acct_id in members_of(db, GROUP, principal_id):
                _consider(acct_id, role, via)

    if not best:
        return []
    emails = {
        aid: email
        for aid, email in db.query(Account.id, Account.email).filter(Account.id.in_(best.keys())).all()
    }
    return [
        {"account_id": aid, "email": emails.get(aid), "role": info["role"], "via": info["via"]}
        for aid, info in sorted(best.items())
    ]


def _role_priority(role: str) -> int:
    """Ordering for 'best role wins' in audit (owner highest)."""
    return {"read": 1, "use": 1, "write": 2, "owner": 3}.get(role, 0)


def resources_for_account(db: Session, account_id: int) -> list:
    """
    Reverse audit: every resource *account_id* can reach via grants (direct or
    group), with the role and path. Does NOT include resources it owns (callers
    add those if needed). Returns list of
    {resource_type, resource_id, role, via}.
    """
    group_rows = (
        db.query(AccessGroupMember.access_group_id)
        .filter(AccessGroupMember.account_id == account_id)
        .all()
    )
    group_ids = {r[0] for r in group_rows}
    group_names = {
        gid: name for gid, name in db.query(AccessGroup.id, AccessGroup.name).all()
    }

    grants = (
        db.query(
            AccessGrant.resource_type,
            AccessGrant.resource_id,
            AccessGrant.role,
            AccessGrant.principal_type,
            AccessGrant.principal_id,
        )
        .filter(
            (
                (AccessGrant.principal_type == ACCOUNT)
                & (AccessGrant.principal_id == account_id)
            )
            | (
                (AccessGrant.principal_type == GROUP)
                & (AccessGrant.principal_id.in_(group_ids) if group_ids else False)
            )
        )
        .all()
    )

    best: dict = {}  # (rtype, rid) -> {role, via}
    for rtype, rid, role, ptype, pid in grants:
        via = "direct" if ptype == ACCOUNT else f"group:{group_names.get(pid, pid)}"
        key = (rtype, rid)
        cur = best.get(key)
        if cur is None or _role_priority(role) > _role_priority(cur["role"]):
            best[key] = {"role": role, "via": via}

    return [
        {"resource_type": rtype, "resource_id": rid, "role": info["role"], "via": info["via"]}
        for (rtype, rid), info in best.items()
    ]
