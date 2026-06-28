"""
Credential access control + default resolution (over the unified resolver).

Credential sharing is now stored as AccessGrant rows (resource_type='credential',
role='use') and resolved by services/access.py. This module keeps the
credential-centric helpers — access checks delegate to access.py; the default
selection / pruning logic is credential-specific and lives here.

USE, not VIEW: a recipient may use a shared credential (the server decrypts it on
their behalf) but the plaintext is never returned — the /full endpoints stay
owner-only.

CANONICAL FILE. Mirrored byte-for-byte into kalygo3-agent-api
(src/services/credential_access.py) via the repo-root sync scripts. Edit the ai-api
copy, then run ./sync-schemas.sh.
"""
from sqlalchemy.orm import Session

from src.db.models import Credential, CredentialDefault
from src.services import access


def can_use_credential(db: Session, account_id: int, credential_id: int) -> bool:
    """True if the account may USE the credential (owner or granted)."""
    return access.can_access(db, account_id, access.CREDENTIAL, credential_id, required="use")


def get_accessible_credential_ids(db: Session, account_id: int) -> set:
    """Credential IDs shared WITH the account (excludes owned)."""
    return access.accessible_resource_ids(db, account_id, access.CREDENTIAL, required="use")


def load_credential_for_use(
    db: Session,
    account_id: int,
    credential_id: int,
) -> "Credential | None":
    """Load and return the credential if *account_id* may use it, else None."""
    credential = db.query(Credential).filter(Credential.id == credential_id).first()
    if credential is None:
        return None
    if credential.account_id == account_id:
        return credential
    return credential if can_use_credential(db, account_id, credential_id) else None


def resolve_default_credential(
    db: Session,
    account_id: int,
    credential_type,
) -> "Credential | None":
    """
    Return the credential the account should use for *credential_type*.

    1. The account's explicitly chosen default for this type, if still usable.
    2. Fallback: the account's own most-recently-updated credential of this type,
       else any accessible shared credential of this type.
    """
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
    Delete the account's default selections whose backing credential it can no
    longer use (e.g. after an unshare or losing group membership). Idempotent;
    caller commits. Returns the number removed.
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
