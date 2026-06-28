"""
Mark a credential as the current user's default for its credential type.

The default is per-account and per-credential-type, and may point at a credential
the user owns OR one shared with them. Setting a new default for a type replaces
any previous one (enforced by a unique constraint on (account_id, credential_type)).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential, CredentialDefault
from src.services.credential_access import can_use_credential
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.put("/{credential_id}/default", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def set_default_credential(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """Set this credential as the caller's default for its type. Requires usage access."""
    try:
        account_id = account_id_from_claims(jwt)
        ensure_account(db, account_id)

        credential = db.query(Credential).filter(Credential.id == credential_id).first()
        if not credential or not can_use_credential(db, account_id, credential_id):
            # Hide existence of credentials the caller cannot use.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        existing = db.query(CredentialDefault).filter(
            CredentialDefault.account_id == account_id,
            CredentialDefault.credential_type == credential.credential_type,
        ).first()

        if existing:
            existing.credential_id = credential_id
        else:
            db.add(CredentialDefault(
                account_id=account_id,
                credential_type=credential.credential_type,
                credential_id=credential_id,
            ))

        db.commit()
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[SET DEFAULT CREDENTIAL]")
