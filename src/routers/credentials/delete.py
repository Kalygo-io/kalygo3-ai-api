"""
Delete credential endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from src.services import access
from src.services.access_admin import revoke_resource_grants_logged
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_credential(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """Delete a credential belonging to the authenticated user."""
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id
        ).first()

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )

        # Remove any sharing grants on this credential (polymorphic grants have no
        # FK cascade), logging a revoke event for each. Per-account default rows
        # clear via the credential_defaults FK ON DELETE CASCADE.
        revoke_resource_grants_logged(
            db, resource_type=access.CREDENTIAL, resource_id=credential_id, actor_account_id=account_id
        )

        db.delete(credential)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR DELETING CREDENTIAL]")
