from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account, CredentialType
from src.db.service_name import ServiceName
from .encryption import (
    encrypt_api_key, 
    decrypt_api_key,
    encrypt_credential_data,
    decrypt_credential_data,
    get_credential_value
)

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS - Legacy (Backward Compatible)
# =============================================================================

class CreateCredentialRequest(BaseModel):
    """Legacy request for creating API key credentials."""
    service_name: ServiceName
    api_key: str


class UpdateCredentialRequest(BaseModel):
    """Legacy request for updating API key credentials."""
    api_key: str


class CredentialResponse(BaseModel):
    """Response model for credential metadata (no sensitive data)."""
    id: int
    service_name: ServiceName
    credential_type: str = "api_key"
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CredentialDetailResponse(BaseModel):
    """Response model with decrypted API key (legacy)."""
    id: int
    service_name: ServiceName
    credential_type: str = "api_key"
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
    - API Key: {"service_name": "OPENAI_API_KEY", "credential_type": "api_key", "credential_data": {"api_key": "sk-..."}}
    - Database: {"service_name": "MY_DATABASE", "credential_type": "db_connection", "credential_data": {"host": "...", "port": 5432, ...}}
    """
    service_name: ServiceName
    credential_type: str = Field(default="api_key", description="Type of credential: api_key, db_connection, oauth, ssh_key, certificate")
    credential_data: Dict[str, Any] = Field(..., description="The credential data structure (varies by type)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Non-sensitive metadata (display name, description, etc.)")


class UpdateFlexibleCredentialRequest(BaseModel):
    """Request for updating any type of credential."""
    credential_data: Dict[str, Any] = Field(..., description="The new credential data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Updated metadata")


class FlexibleCredentialDetailResponse(BaseModel):
    """Response model with full decrypted credential data."""
    id: int
    service_name: ServiceName
    credential_type: str
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
        # Get the account from the database using the JWT account_id
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Check if a credential for this service already exists
        existing_credential = db.query(Credential).filter(
            Credential.account_id == account_id,
            Credential.service_name == request_body.service_name
        ).first()
        
        if existing_credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential for service '{request_body.service_name.value}' already exists. Use PUT to update it."
            )
        
        # Encrypt the API key using the new format (for forward compatibility)
        encrypted_data = encrypt_credential_data({"api_key": request_body.api_key})
        
        # Also store in legacy column for backward compatibility
        encrypted_key = encrypt_api_key(request_body.api_key)
        
        # Create the credential with both new and legacy fields
        credential = Credential(
            account_id=account_id,
            service_name=request_body.service_name,
            credential_type="api_key",
            encrypted_data=encrypted_data,
            encrypted_api_key=encrypted_key  # Legacy, for backward compatibility
        )
        
        db.add(credential)
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        print(f"Error creating credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating credential: {str(e)}"
        )


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
                service_name=cred.service_name,
                credential_type=cred.credential_type or "api_key",
                created_at=cred.created_at.isoformat(),
                updated_at=cred.updated_at.isoformat(),
                credential_metadata=cred.credential_metadata
            )
            for cred in credentials
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing credentials: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing credentials: {str(e)}"
        )


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
        
        # Use backward-compatible decryption (prefers encrypted_data, falls back to encrypted_api_key)
        decrypted_key = get_credential_value(credential, "api_key")
        
        return CredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type or "api_key",
            api_key=decrypted_key,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error retrieving credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving credential: {str(e)}"
        )


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
    Only allows updating credentials belonging to the authenticated user.
    
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
        
        # Encrypt using new format
        encrypted_data = encrypt_credential_data({"api_key": request_body.api_key})
        
        # Also update legacy column for backward compatibility
        encrypted_key = encrypt_api_key(request_body.api_key)
        
        # Update the credential with both formats
        credential.encrypted_data = encrypted_data
        credential.encrypted_api_key = encrypted_key  # Legacy, for backward compatibility
        credential.credential_type = "api_key"
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        print(f"Error updating credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating credential: {str(e)}"
        )


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_credential(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Delete a credential.
    Only allows deleting credentials belonging to the authenticated user.
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
        
        db.delete(credential)
        db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting credential: {str(e)}"
        )


@router.get("/service/{service_name}", response_model=CredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_by_service(
    service_name: ServiceName,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a credential by service name, including the decrypted API key.
    Useful for retrieving a specific service's API key.
    
    LEGACY ENDPOINT: Returns api_key field for backward compatibility.
    For full credential data (DB connections, etc.), use GET /service/{service_name}/full
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
            Credential.service_name == service_name
        ).first()
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential for service '{service_name.value}' not found"
            )
        
        # Use backward-compatible decryption
        decrypted_key = get_credential_value(credential, "api_key")
        
        return CredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type or "api_key",
            api_key=decrypted_key,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error retrieving credential by service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving credential: {str(e)}"
        )


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
    
    Example request:
    {
        "service_name": "OPENAI_API_KEY",
        "credential_type": "api_key",
        "credential_data": {"api_key": "sk-abc123..."},
        "metadata": {"display_name": "Production API Key"}
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
        
        # Check if a credential for this service already exists
        existing_credential = db.query(Credential).filter(
            Credential.account_id == account_id,
            Credential.service_name == request_body.service_name
        ).first()
        
        if existing_credential:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Credential for service '{request_body.service_name.value}' already exists. Use PUT to update it."
            )
        
        # Encrypt the credential data
        encrypted_data = encrypt_credential_data(request_body.credential_data)
        
        # For API keys, also populate legacy column for backward compatibility
        encrypted_api_key = None
        if request_body.credential_type == "api_key" and "api_key" in request_body.credential_data:
            encrypted_api_key = encrypt_api_key(request_body.credential_data["api_key"])
        
        # Create the credential
        credential = Credential(
            account_id=account_id,
            service_name=request_body.service_name,
            credential_type=request_body.credential_type,
            encrypted_data=encrypted_data,
            encrypted_api_key=encrypted_api_key,
            credential_metadata=request_body.metadata
        )
        
        db.add(credential)
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        print(f"Error creating flexible credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating credential: {str(e)}"
        )


@router.get("/{credential_id}/full", response_model=FlexibleCredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_full(
    credential_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a specific credential with full decrypted data structure.
    Use this for flexible credentials (DB connections, OAuth, etc.).
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
        
        # Decrypt the full credential data
        if credential.encrypted_data:
            credential_data = decrypt_credential_data(credential.encrypted_data)
        elif credential.encrypted_api_key:
            # Backward compatibility: wrap legacy API key
            credential_data = {"api_key": decrypt_api_key(credential.encrypted_api_key)}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No encrypted credential data found"
            )
        
        return FlexibleCredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type or "api_key",
            credential_data=credential_data,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error retrieving full credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving credential: {str(e)}"
        )


@router.put("/{credential_id}/full", response_model=CredentialResponse)
@limiter.limit("10/minute")
async def update_credential_full(
    credential_id: int,
    request_body: UpdateFlexibleCredentialRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Update a credential with full flexible data structure.
    Use this for flexible credentials (DB connections, OAuth, etc.).
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
        
        # Encrypt the new credential data
        encrypted_data = encrypt_credential_data(request_body.credential_data)
        
        # For API keys, also update legacy column for backward compatibility
        if "api_key" in request_body.credential_data:
            credential.encrypted_api_key = encrypt_api_key(request_body.credential_data["api_key"])
        
        # Update the credential
        credential.encrypted_data = encrypted_data
        if request_body.metadata is not None:
            credential.credential_metadata = request_body.metadata
        
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        print(f"Error updating flexible credential: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating credential: {str(e)}"
        )


@router.get("/service/{service_name}/full", response_model=FlexibleCredentialDetailResponse)
@limiter.limit("30/minute")
async def get_credential_by_service_full(
    service_name: ServiceName,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a credential by service name with full decrypted data structure.
    Use this for flexible credentials (DB connections, OAuth, etc.).
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
            Credential.service_name == service_name
        ).first()
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential for service '{service_name.value}' not found"
            )
        
        # Decrypt the full credential data
        if credential.encrypted_data:
            credential_data = decrypt_credential_data(credential.encrypted_data)
        elif credential.encrypted_api_key:
            # Backward compatibility: wrap legacy API key
            credential_data = {"api_key": decrypt_api_key(credential.encrypted_api_key)}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No encrypted credential data found"
            )
        
        return FlexibleCredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            credential_type=credential.credential_type or "api_key",
            credential_data=credential_data,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat(),
            credential_metadata=credential.credential_metadata
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        print(f"Error retrieving full credential by service: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving credential: {str(e)}"
        )

