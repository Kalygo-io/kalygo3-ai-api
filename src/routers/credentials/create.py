"""
Create credential endpoint (legacy).
"""
import logging
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from .encryption import encrypt_credential_data
from .models import CreateCredentialRequest, CredentialResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CredentialResponse)
@limiter.limit("10/minute")
async def create_credential(
    request_body: CreateCredentialRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new credential (API key) for a third-party service.
    The API key will be encrypted before storage.

    LEGACY ENDPOINT: For simple API key storage.
    For flexible credentials (DB connections, OAuth, etc.), use POST /flexible
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)

        encrypted_data = encrypt_credential_data({"api_key": request_body.api_key})

        credential = Credential(
            account_id=account_id,
            credential_type=request_body.credential_type,
            auth_type="api_key",
            encrypted_data=encrypted_data
        )

        db.add(credential)
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
        logger.error('[CREDENTIALS] ValueError creating credential: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR CREATING CREDENTIAL]")
