"""
Update credential endpoint (legacy).
"""
import logging
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account
from .encryption import encrypt_credential_data
from .models import UpdateCredentialRequest, CredentialResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.put("/{credential_id}", response_model=CredentialResponse)
@limiter.limit("10/minute")
async def update_credential(
    credential_id: int,
    request_body: UpdateCredentialRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Update an existing credential's API key.

    LEGACY ENDPOINT: For simple API key updates.
    For flexible credentials, use PUT /{id}/full
    """
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

        encrypted_data = encrypt_credential_data({"api_key": request_body.api_key})

        credential.encrypted_data = encrypted_data
        credential.auth_type = "api_key"
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
        logger.error('[CREDENTIALS] ValueError updating credential: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR UPDATING CREDENTIAL]")
