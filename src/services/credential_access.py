"""
Centralized credential access control + default resolution.

Single source of truth for "can this account USE this credential?" and "which
credential is this account's default for a given type?".

CANONICAL FILE. This module is mirrored byte-for-byte into kalygo3-agent-api
(src/services/credential_access.py). The ai-api copy is canonical; the agent-api
copy is kept in sync by the repo-root scripts (schema-files.sh / check-schemas.sh
/ sync-schemas.sh). Edit the ai-api copy, then run ./sync-schemas.sh. Do not edit
the two copies independently.

Access rule (USE, not VIEW — recipients can use a shared credential but the
plaintext is never returned to them; the /full endpoints stay owner-only):
  An account can USE a credential if ANY of
    1. it owns the credential (credential.account_id == account_id), OR
    2. the credential is shared with it directly (an individual grant), OR
    3. it is a member of an access group the credential is shared with.
"""
from sqlalchemy.orm import Session
from sqlalchemy import exists, and_

from src.db.models import (
    Credential,
    CredentialAccessGrant,
    CredentialDefault,
    AccessGroupMember,
)


def _group_grant_exists(db: Session, account_id: int, credential_id: int):
    """Single indexed EXISTS: a group grant to a group the account belongs to."""
    return db.query(
        exists().where(
            and_(
                CredentialAccessGrant.credential_id == credential_id,
                CredentialAccessGrant.access_group_id == AccessGroupMember.access_group_id,
                AccessGroupMember.account_id == account_id,
            )
        )
    ).scalar()


def _individual_grant_exists(db: Session, account_id: int, credential_id: int):
    """Single indexed EXISTS: a direct individual grant to the account."""
    return db.query(
        exists().where(
            and_(
                CredentialAccessGrant.credential_id == credential_id,
                CredentialAccessGrant.grantee_account_id == account_id,
            )
        )
    ).scalar()


def can_use_credential(db: Session, account_id: int, credential_id: int) -> bool:
    """
    Return True if the account may USE the credential.

    A PK lookup for ownership, then (if not owner) at most two indexed EXISTS
    checks for an individual grant or a group grant.
    """
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    if not credential:
        return False

    # Owner always has access
    if credential.account_id == account_id:
        return True

    if _individual_grant_exists(db, account_id, credential_id):
        return True

    return bool(_group_grant_exists(db, account_id, credential_id))


def get_accessible_credential_ids(db: Session, account_id: int) -> set:
    """
    Return the set of credential IDs shared WITH the account (individual grants +
    grants to groups the account belongs to). Does NOT include credentials the
    account owns -- the caller unions those separately (see credentials/list.py).
    """
    individual = (
        db.query(CredentialAccessGrant.credential_id)
        .filter(CredentialAccessGrant.grantee_account_id == account_id)
    )
    via_group = (
        db.query(CredentialAccessGrant.credential_id)
        .join(
            AccessGroupMember,
            AccessGroupMember.access_group_id == CredentialAccessGrant.access_group_id,
        )
        .filter(AccessGroupMember.account_id == account_id)
    )
    return {r[0] for r in individual.union(via_group).all()}


def load_credential_for_use(
    db: Session,
    account_id: int,
    credential_id: int,
) -> "Credential | None":
    """
    Load and return the credential if *account_id* may use it, else None.

    Convenience wrapper so consumers (email send, Pinecone, GCS, etc.) can fetch
    the Credential object and authorize in one call. Applies the exact same rule
    as can_use_credential.
    """
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    if credential is None:
        return None

    if credential.account_id == account_id:
        return credential

    if _individual_grant_exists(db, account_id, credential_id):
        return credential

    if _group_grant_exists(db, account_id, credential_id):
        return credential

    return None


def resolve_default_credential(
    db: Session,
    account_id: int,
    credential_type,
) -> "Credential | None":
    """
    Return the credential the account should use for *credential_type*.

    1. The account's explicitly chosen default for this type, if it still has
       access to that credential.
    2. Fallback (preserves prior behavior for accounts that never set a default):
       the account's own most-recently-updated credential of this type, else any
       accessible shared credential of this type.
    """
    # 1. Explicit default (validate access in case sharing changed underneath it).
    default = (
        db.query(CredentialDefault)
        .filter(
            CredentialDefault.account_id == account_id,
            CredentialDefault.credential_type == credential_type,
        )
        .first()
    )
    if default and can_use_credential(db, account_id, default.credential_id):
        return db.query(Credential).filter(Credential.id == default.credential_id).first()

    # 2a. Owned credential of this type (most recent).
    owned = (
        db.query(Credential)
        .filter(
            Credential.account_id == account_id,
            Credential.credential_type == credential_type,
        )
        .order_by(Credential.updated_at.desc())
        .first()
    )
    if owned:
        return owned

    # 2b. Any accessible shared credential of this type.
    shared_ids = get_accessible_credential_ids(db, account_id)
    if not shared_ids:
        return None
    return (
        db.query(Credential)
        .filter(
            Credential.id.in_(shared_ids),
            Credential.credential_type == credential_type,
        )
        .order_by(Credential.updated_at.desc())
        .first()
    )


def prune_unusable_defaults_for_account(db: Session, account_id: int) -> int:
    """
    Delete any of the account's default selections whose backing credential it can
    no longer use (e.g. after a credential is unshared, or the account is removed
    from a group that was the only path to that credential).

    Idempotent. Returns the number of defaults removed. The caller is responsible
    for committing. Centralizes the "unshare clears default" invariant so every
    access-removing path can call one helper. (Credential deletion needs no call
    here -- credential_defaults.credential_id cascades.)
    """
    defaults = (
        db.query(CredentialDefault)
        .filter(CredentialDefault.account_id == account_id)
        .all()
    )
    removed = 0
    for d in defaults:
        if not can_use_credential(db, account_id, d.credential_id):
            db.delete(d)
            removed += 1
    return removed
