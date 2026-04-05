from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account, CredentialType
from src.db.service_name import ServiceName
from .encryption import (
    encrypt_credential_data,
    decrypt_credential_data,
    get_credential_value
)

from slowapi import Limiter
from slowapi.util import get_remote_address
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS - Legacy (Backward Compatible)
# =============================================================================

class CreateCredentialRequest(BaseModel):
    """Legacy request for creating API key credentials."""
    credential_type: ServiceName
    api_key: str


class UpdateCredentialRequest(BaseModel):
    """Legacy request for updating API key credentials."""
    api_key: str


class CredentialResponse(BaseModel):
    """Response model for credential metadata (no sensitive data)."""
    id: int
    credential_type: ServiceName
    auth_type: str = "api_key"
    credential_name: Optional[str] = None
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CredentialDetailResponse(BaseModel):
    """Response model with decrypted API key (legacy)."""
    id: int
    credential_type: ServiceName
    auth_type: str = "api_key"
    credential_name: Optional[str] = None
    api_key: str  # Decrypted API key (only returned when explicitly requested)
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# =============================================================================
# REQUEST/RESPONSE MODELS - New Flexible Format
# =============================================================================

class CreateFlexibleCredentialRequest(BaseModel):
    """
    Request for creating any type of credential.

    Examples:
    - API Key: {"credential_type": "OPENAI_API_KEY", "auth_type": "api_key", "credential_data": {"api_key": "sk-..."}}
    - Database: {"credential_type": "SUPABASE", "auth_type": "db_connection", "credential_data": {"host": "...", ...}}
    """
    credential_type: ServiceName
    auth_type: str = Field(default="api_key", description="Auth mechanism: api_key, db_connection, oauth, ssh_key, certificate, aws_access_key_pair")
    credential_name: Optional[str] = Field(default=None, description="Human-readable name for this credential (e.g. 'Production', 'Staging')")
    credential_data: Dict[str, Any] = Field(..., description="The credential data structure (varies by auth_type)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Non-sensitive metadata (notes, environment, etc.)")


class UpdateFlexibleCredentialRequest(BaseModel):
    """Request for updating any type of credential."""
    credential_name: Optional[str] = Field(default=None, description="Updated human-readable name")
    credential_data: Dict[str, Any] = Field(..., description="The new credential data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Updated metadata")


class FlexibleCredentialDetailResponse(BaseModel):
    """Response model with full decrypted credential data."""
    id: int
    credential_type: ServiceName
    auth_type: str
    credential_name: Optional[str] = None
    credential_data: Dict[str, Any]  # Decrypted credential structure
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


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
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR CREATING CREDENTIAL]")


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
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING CREDENTIAL]")


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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR UPDATING CREDENTIAL]")


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


@router.get("/service/{service_name}", response_model=CredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_by_service(
    service_name: ServiceName,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a credential by service/provider type (first match), including the decrypted API key.

    LEGACY ENDPOINT: Returns api_key field for backward compatibility.
    For full credential data, use GET /service/{service_name}/full
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
            Credential.account_id == account_id,
            Credential.credential_type == service_name
        ).first()

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential for service '{service_name.value}' not found"
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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING CREDENTIAL BY SERVICE]")


# =============================================================================
# NEW FLEXIBLE CREDENTIAL ENDPOINTS
# =============================================================================

@router.post("/flexible", status_code=status.HTTP_201_CREATED, response_model=CredentialResponse)
@limiter.limit("10/minute")
async def create_flexible_credential(
    request_body: CreateFlexibleCredentialRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new flexible credential for any type of service.

    Supports:
    - API keys: {"api_key": "sk-..."}
    - Database connections: {"host": "...", "port": 5432, "username": "...", "password": "...", "database": "..."}
    - OAuth: {"client_id": "...", "client_secret": "...", "access_token": "...", "refresh_token": "..."}
    - SSH keys: {"private_key": "-----BEGIN...", "passphrase": "..."}
    - Certificates: {"certificate": "...", "private_key": "..."}
    - AWS access key pairs: {"aws_access_key_id": "AKIA...", "aws_secret_access_key": "...", "aws_region": "...", "from_email": "..."}

    Example request:
    {
        "credential_type": "OPENAI_API_KEY",
        "auth_type": "api_key",
        "credential_name": "Production",
        "credential_data": {"api_key": "sk-abc123..."},
        "metadata": {"notes": "Main production key"}
    }
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        encrypted_data = encrypt_credential_data(request_body.credential_data)

        credential = Credential(
            account_id=account_id,
            credential_type=request_body.credential_type,
            auth_type=request_body.auth_type,
            credential_name=request_body.credential_name,
            encrypted_data=encrypted_data,
            credential_metadata=request_body.metadata
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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR CREATING FLEXIBLE CREDENTIAL]")


@router.get("/{credential_id}/full", response_model=FlexibleCredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_full(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """Get a specific credential with full decrypted data structure."""
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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING FULL CREDENTIAL]")


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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR UPDATING FLEXIBLE CREDENTIAL]")


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
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

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
        import logging as _log
        _log.getLogger(__name__).error('[CREDENTIALS] ValueError: %s', e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid credential data.',
        )
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING FULL CREDENTIAL BY SERVICE]")
