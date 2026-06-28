"""
List credentials endpoint.

Returns credentials the authenticated user owns as well as credentials shared
with them (directly or via an access group). Each item carries ``is_owner``,
``is_default`` (the caller's default for that type), and ``shared_label`` so the
UI can split them into "My Credentials" / "Shared with me" sections.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import or_
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import (
    Credential,
    AccessGrant,
    CredentialDefault,
    AccessGroup,
    AccessGroupMember,
    Account,
)
from src.services import access
from src.services.credential_access import get_accessible_credential_ids
from .models import CredentialResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/", response_model=List[CredentialResponse])
@limiter.limit("30/minute")
async def list_credentials(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all credentials the authenticated user can access (owned + shared).
    Returns metadata only (no decrypted secrets, even for shared credentials).
    """
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)

        # IDs shared with the caller (excludes owned).
        shared_ids = get_accessible_credential_ids(db, account_id)

        if shared_ids:
            credentials = (
                db.query(Credential)
                .filter(
                    or_(
                        Credential.account_id == account_id,
                        Credential.id.in_(shared_ids),
                    )
                )
                .order_by(Credential.id.desc())
                .all()
            )
        else:
            credentials = (
                db.query(Credential)
                .filter(Credential.account_id == account_id)
                .order_by(Credential.id.desc())
                .all()
            )

        # The caller's default credential ids (one per type) for is_default tagging.
        default_ids = {
            r[0]
            for r in db.query(CredentialDefault.credential_id)
            .filter(CredentialDefault.account_id == account_id)
            .all()
        }

        # Build shared_label for credentials NOT owned by the caller. Prefer a
        # direct-share label ("Shared by <owner email>"); fall back to the group
        # name(s) the caller reached it through.
        shared_labels = _build_shared_labels(db, account_id, shared_ids) if shared_ids else {}

        return [
            CredentialResponse(
                id=cred.id,
                credential_type=cred.credential_type,
                auth_type=cred.auth_type or "api_key",
                credential_name=cred.credential_name,
                created_at=cred.created_at.isoformat(),
                updated_at=cred.updated_at.isoformat(),
                credential_metadata=cred.credential_metadata,
                is_owner=(cred.account_id == account_id),
                is_default=(cred.id in default_ids),
                shared_label=(None if cred.account_id == account_id else shared_labels.get(cred.id)),
            )
            for cred in credentials
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR LISTING CREDENTIALS]")


def _build_shared_labels(db, account_id: int, shared_ids: set) -> dict:
    """
    Map each shared credential id -> a human-readable label describing how the
    caller can access it. Direct individual shares win ("Shared by <owner>");
    otherwise the access-group name is used.
    """
    labels: dict = {}

    # Individual shares to this account: label with the owner's email.
    direct_rows = (
        db.query(AccessGrant.resource_id, Account.email)
        .join(Credential, Credential.id == AccessGrant.resource_id)
        .join(Account, Account.id == Credential.account_id)
        .filter(
            AccessGrant.resource_type == access.CREDENTIAL,
            AccessGrant.principal_type == access.ACCOUNT,
            AccessGrant.principal_id == account_id,
            AccessGrant.resource_id.in_(shared_ids),
        )
        .all()
    )
    for cred_id, owner_email in direct_rows:
        labels[cred_id] = f"Shared by {owner_email}"

    # Group shares the caller reaches via membership: label with the group name.
    group_rows = (
        db.query(AccessGrant.resource_id, AccessGroup.name)
        .join(AccessGroup, AccessGroup.id == AccessGrant.principal_id)
        .join(AccessGroupMember, AccessGroupMember.access_group_id == AccessGroup.id)
        .filter(
            AccessGrant.resource_type == access.CREDENTIAL,
            AccessGrant.principal_type == access.GROUP,
            AccessGroupMember.account_id == account_id,
            AccessGrant.resource_id.in_(shared_ids),
        )
        .all()
    )
    for cred_id, group_name in group_rows:
        labels.setdefault(cred_id, f"Shared via {group_name}")

    return labels
