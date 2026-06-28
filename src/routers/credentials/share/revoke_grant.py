"""
Revoke a credential access grant (credential owner only).

Revoking access also clears any now-orphaned default selections: if the revoked
account(s) can no longer use the credential, their default for that credential's
type is removed (requirement: "unsharing removes default").
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential, CredentialAccessGrant, AccessGroupMember
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

        grant = db.query(CredentialAccessGrant).filter(
            CredentialAccessGrant.id == grant_id,
            CredentialAccessGrant.credential_id == credential_id,
        ).first()
        if not grant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

        # Determine which accounts lose this path of access (so we can prune their
        # now-orphaned defaults). Capture before deleting the grant.
        if grant.grantee_account_id is not None:
            affected_account_ids = [grant.grantee_account_id]
        else:
            member_rows = (
                db.query(AccessGroupMember.account_id)
                .filter(AccessGroupMember.access_group_id == grant.access_group_id)
                .all()
            )
            affected_account_ids = [r[0] for r in member_rows]

        db.delete(grant)
        db.flush()  # apply the delete so access re-checks reflect it

        for acct_id in affected_account_ids:
            prune_unusable_defaults_for_account(db, acct_id)

        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REVOKE CREDENTIAL GRANT]")
