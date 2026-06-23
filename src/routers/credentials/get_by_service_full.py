"""
Get credential by service name with full decrypted data endpoint.
"""
import logging
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from src.db.service_name import ServiceName
from .encryption import decrypt_credential_data
from .models import FlexibleCredentialDetailResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/service/{service_name}/full", response_model=FlexibleCredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_by_service_full(
    service_name: ServiceName,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a credential by service/provider type (first match) with full decrypted data.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)

        credential = db.query(Credential).filter(
            Credential.account_id == account_id,
            Credential.credential_type == service_name
        ).first()

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential for service '{service_name.value}' not found"
            )

        credential_data = decrypt_credential_data(credential.encrypted_data)

        return FlexibleCredentialDetailResponse(
            id=credential.id,
            credential_type=credential.credential_type,
            auth_type=credential.auth_type,
            credential_name=credential.credential_name,
            credential_data=credential_data,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error('[CREDENTIALS] ValueError retrieving full credential by service: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING FULL CREDENTIAL BY SERVICE]")
