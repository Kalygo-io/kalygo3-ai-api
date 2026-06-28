"""
Revoke a credential access grant (credential owner only).

Removing access also clears any now-orphaned default selections for the affected
account(s) ("unsharing removes default").
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential, AccessGrant, AccessGroupMember
from src.services import access
from src.services.credential_access import prune_unusable_defaults_for_account
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.delete("/{credential_id}/access-grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_credential_grant(
    credential_id: int,
    grant_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Remove a share. Credential owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        grant = db.query(AccessGrant).filter(
            AccessGrant.id == grant_id,
            AccessGrant.resource_type == access.CREDENTIAL,
            AccessGrant.resource_id == credential_id,
        ).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        # Accounts losing this access path → prune their orphaned defaults after delete.
        if grant.principal_type == access.ACCOUNT:
            affected = [grant.principal_id]
        else:
            affected = [
                r[0]
                for r in db.query(AccessGroupMember.account_id)
                .filter(AccessGroupMember.access_group_id == grant.principal_id)
                .all()
            ]

        db.delete(grant)
        db.flush()
        for acct_id in affected:
            prune_unusable_defaults_for_account(db, acct_id)

        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE CREDENTIAL GRANT]")
