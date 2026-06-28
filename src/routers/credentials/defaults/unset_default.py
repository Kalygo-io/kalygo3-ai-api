"""
Clear the current user's default for a credential's type.

Only clears the default if it currently points at this credential, so a stale
client cannot accidentally clear a different credential's default.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import CredentialDefault
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.delete("/{credential_id}/default", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def unset_default_credential(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Remove the caller's default if it points at this credential."""
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)

        default = db.query(CredentialDefault).filter(
            CredentialDefault.account_id == account_id,
            CredentialDefault.credential_id == credential_id,
        ).first()

        if default:
            db.delete(default)
            db.commit()

        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UNSET DEFAULT CREDENTIAL]")
