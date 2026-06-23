"""
Update credential with full flexible data endpoint.
"""
import logging
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from .encryption import encrypt_credential_data
from .models import UpdateFlexibleCredentialRequest, CredentialResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put("/{credential_id}/full", response_model=CredentialResponse)
@limiter.limit("10/minute")
async def update_credential_full(
    credential_id: int,
    request_body: UpdateFlexibleCredentialRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """Update a credential with full flexible data structure."""
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

        encrypted_data = encrypt_credential_data(request_body.credential_data)

        credential.encrypted_data = encrypted_data
        if request_body.credential_name is not None:
            credential.credential_name = request_body.credential_name
        if request_body.metadata is not None:
            credential.credential_metadata = request_body.metadata

        db.commit()
        db.refresh(credential)

        return CredentialResponse(
            id=credential.id,
            credential_type=credential.credential_type,
            auth_type=credential.auth_type,
            credential_name=credential.credential_name,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )

    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        logger.error('[CREDENTIALS] ValueError updating flexible credential: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR UPDATING FLEXIBLE CREDENTIAL]")
