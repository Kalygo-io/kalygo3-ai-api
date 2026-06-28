"""
List the access grants on a credential (credential owner only).
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential
from src.services import access
from src.services.access_admin import list_resource_grants, grant_label
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

        grants = list_resource_grants(db, access.CREDENTIAL, credential_id)
        return [
            CredentialGrantResponse(
                id=g.id,
                credential_id=credential_id,
                access_group_id=g.principal_id if g.principal_type == access.GROUP else None,
                grantee_account_id=g.principal_id if g.principal_type == access.ACCOUNT else None,
                label=grant_label(db, g),
                target_type="group" if g.principal_type == access.GROUP else "individual",
                created_at=g.created_at,
            )
            for g in grants
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CREDENTIAL GRANTS]")
