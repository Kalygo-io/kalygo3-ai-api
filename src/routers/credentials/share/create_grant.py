"""
Share a credential with an access group or an individual (credential owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import Credential, AccessGroup, Account, CredentialAccessGrant
from src.services.access_group_roles import is_group_manager
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
    """
    Share a credential with an access group OR an individual account.

    Only the credential OWNER may share. For a group target the owner must also
    be a manager (owner/admin) of that group — matching the agent-grant rule.
    Recipients may USE the credential but never receive its plaintext.
    """
    try:
        account_id = account_id_from_claims(jwt)

        # Only the owner can share.
        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()
        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        if body.accessGroupId is not None:
            # ── Group target ──────────────────────────────────────────────────
            group = db.query(AccessGroup).filter(AccessGroup.id == body.accessGroupId).first()
            if not group:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
            if not is_group_manager(db, group, account_id):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to share with this group")

            existing = db.query(CredentialAccessGrant).filter(
                CredentialAccessGrant.credential_id == credential_id,
                CredentialAccessGrant.access_group_id == body.accessGroupId,
            ).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential is already shared with this group")

            grant = CredentialAccessGrant(
                credential_id=credential_id,
                access_group_id=body.accessGroupId,
            )
            db.add(grant)
            db.commit()
            db.refresh(grant)

            return CredentialGrantResponse(
                id=grant.id,
                credential_id=grant.credential_id,
                access_group_id=grant.access_group_id,
                grantee_account_id=None,
                label=group.name,
                target_type="group",
                created_at=grant.created_at,
            )

        # ── Individual target ─────────────────────────────────────────────────
        target = db.query(Account).filter(Account.email == body.granteeEmail).first()
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found for the given email")
        if target.id == account_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this credential")

        existing = db.query(CredentialAccessGrant).filter(
            CredentialAccessGrant.credential_id == credential_id,
            CredentialAccessGrant.grantee_account_id == target.id,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Credential is already shared with this account")

        grant = CredentialAccessGrant(
            credential_id=credential_id,
            grantee_account_id=target.id,
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)

        return CredentialGrantResponse(
            id=grant.id,
            credential_id=grant.credential_id,
            access_group_id=None,
            grantee_account_id=grant.grantee_account_id,
            label=target.email,
            target_type="individual",
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CREDENTIAL GRANT]")
