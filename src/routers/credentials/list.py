"""
List credentials endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Credential
from .models import CredentialResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/", response_model=List[CredentialResponse])
@limiter.limit("30/minute")
async def list_credentials(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all credentials for the authenticated user.
    Returns metadata only (no decrypted secrets).
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)

        credentials = db.query(Credential).filter(
            Credential.account_id == account_id
        ).all()

        return [
            CredentialResponse(
                id=cred.id,
                credential_type=cred.credential_type,
                auth_type=cred.auth_type or "api_key",
                credential_name=cred.credential_name,
                created_at=cred.created_at.isoformat(),
                updated_at=cred.updated_at.isoformat(),
                credential_metadata=cred.credential_metadata
            )
            for cred in credentials
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR LISTING CREDENTIALS]")
