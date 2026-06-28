"""
List the access grants on a credential (credential owner only).
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential, AccessGroup, Account, CredentialAccessGrant
from .models import CredentialGrantResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/{credential_id}/access-grants", response_model=List[CredentialGrantResponse])
@limiter.limit("30/minute")
async def list_credential_grants(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """List everyone a credential is shared with. Credential owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        # Join out group names and grantee emails for display labels.
        rows = (
            db.query(CredentialAccessGrant, AccessGroup.name, Account.email)
            .outerjoin(AccessGroup, AccessGroup.id == CredentialAccessGrant.access_group_id)
            .outerjoin(Account, Account.id == CredentialAccessGrant.grantee_account_id)
            .filter(CredentialAccessGrant.credential_id == credential_id)
            .order_by(CredentialAccessGrant.created_at.desc())
            .all()
        )

        return [
            CredentialGrantResponse(
                id=grant.id,
                credential_id=grant.credential_id,
                access_group_id=grant.access_group_id,
                grantee_account_id=grant.grantee_account_id,
                label=(group_name if grant.access_group_id else grantee_email) or "(unknown)",
                target_type="group" if grant.access_group_id else "individual",
                created_at=grant.created_at,
            )
            for grant, group_name, grantee_email in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CREDENTIAL GRANTS]")
