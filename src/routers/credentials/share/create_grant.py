"""
Share a credential with an access group or an individual (credential owner only).

Writes a unified AccessGrant (resource_type='credential', role='use').
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential, AccessGrant
from src.services import access
from src.services.access_admin import resolve_principal, upsert_grant
from .models import CreateCredentialGrantRequest, CredentialGrantResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.post("/{credential_id}/access-grants", response_model=CredentialGrantResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_credential_grant(
    credential_id: int,
    body: CreateCredentialGrantRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Share a credential with a group OR an individual. Owner only. Use-not-view."""
    try:
        account_id = account_id_from_claims(jwt)

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        principal_type, principal_id, label = resolve_principal(
            db,
            caller_account_id=account_id,
            access_group_id=body.accessGroupId,
            grantee_email=body.granteeEmail,
        )

        # Reject duplicate (a grant already exists for this principal on this credential).
        existing = db.query(AccessGrant).filter(
            AccessGrant.principal_type == principal_type,
            AccessGrant.principal_id == principal_id,
            AccessGrant.resource_type == access.CREDENTIAL,
            AccessGrant.resource_id == credential_id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential is already shared with this principal")

        grant = upsert_grant(
            db,
            principal_type=principal_type,
            principal_id=principal_id,
            resource_type=access.CREDENTIAL,
            resource_id=credential_id,
            role="use",
        )
        db.commit()
        db.refresh(grant)

        return CredentialGrantResponse(
            id=grant.id,
            credential_id=credential_id,
            access_group_id=principal_id if principal_type == access.GROUP else None,
            grantee_account_id=principal_id if principal_type == access.ACCOUNT else None,
            label=label,
            target_type="group" if principal_type == access.GROUP else "individual",
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CREDENTIAL GRANT]")
