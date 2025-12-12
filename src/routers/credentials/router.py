from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from typing import Optional, List
from src.deps import db_dependency, jwt_dependency
from src.db.models import Credential, Account
from src.db.service_name import ServiceName
from .encryption import encrypt_api_key, decrypt_api_key

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


class CreateCredentialRequest(BaseModel):
    service_name: ServiceName
    api_key: str


class UpdateCredentialRequest(BaseModel):
    api_key: str


class CredentialResponse(BaseModel):
    id: int
    service_name: ServiceName
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class CredentialDetailResponse(BaseModel):
    id: int
    service_name: ServiceName
    api_key: str  # Decrypted API key (only returned when explicitly requested)
    created_at: str
    updated_at: str

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
        
        # Encrypt the API key
        encrypted_key = encrypt_api_key(request_body.api_key)
        
        # Create the credential
        credential = Credential(
            account_id=account_id,
            service_name=request_body.service_name,
            encrypted_api_key=encrypted_key
        )
        
        db.add(credential)
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat()
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
    Returns metadata only (no decrypted API keys).
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
                created_at=cred.created_at.isoformat(),
                updated_at=cred.updated_at.isoformat()
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
        
        # Decrypt the API key
        decrypted_key = decrypt_api_key(credential.encrypted_api_key)
        
        return CredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            api_key=decrypted_key,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat()
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
        
        # Encrypt the new API key
        encrypted_key = encrypt_api_key(request_body.api_key)
        
        # Update the credential
        credential.encrypted_api_key = encrypted_key
        db.commit()
        db.refresh(credential)
        
        return CredentialResponse(
            id=credential.id,
            service_name=credential.service_name,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat()
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
        
        # Decrypt the API key
        decrypted_key = decrypt_api_key(credential.encrypted_api_key)
        
        return CredentialDetailResponse(
            id=credential.id,
            service_name=credential.service_name,
            api_key=decrypted_key,
            created_at=credential.created_at.isoformat(),
            updated_at=credential.updated_at.isoformat()
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

