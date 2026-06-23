"""
Get credential endpoint (legacy).
"""
import logging
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from .encryption import get_credential_value
from .models import CredentialDetailResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{credential_id}", response_model=CredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a specific credential by ID, including the decrypted API key.
    Only returns credentials belonging to the authenticated user.

    LEGACY ENDPOINT: Returns api_key field for backward compatibility.
    For full credential data (DB connections, etc.), use GET /{id}/full
    """
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

        decrypted_key = get_credential_value(credential, "api_key")

        return CredentialDetailResponse(
            id=credential.id,
            credential_type=credential.credential_type,
            auth_type=credential.auth_type or "api_key",
            credential_name=credential.credential_name,
            api_key=decrypted_key,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error('[CREDENTIALS] ValueError retrieving credential: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING CREDENTIAL]")
