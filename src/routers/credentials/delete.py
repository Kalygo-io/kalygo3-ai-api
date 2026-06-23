"""
Delete credential endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account
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
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id
        ).first()

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credential not found"
            )

        db.delete(credential)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR DELETING CREDENTIAL]")
