"""
Create API key endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import ApiKey, ApiKeyStatus
from src.utils.api_key_utils import generate_api_key
from .models import CreateApiKeyRequest, CreateApiKeyResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CreateApiKeyResponse)
@limiter.limit("10/minute")
async def create_api_key(
    request_body: CreateApiKeyRequest,
    db: db_dependency,
    jwt: jwt_dependency,  # Must be logged in via JWT to create keys
    request: Request
):
    """
    Create a new API key. The full key is returned only once.
    You must be authenticated via JWT to create API keys.
    """
    try:
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Generate key
        full_key, key_hash, key_prefix = generate_api_key()
        
        # Create record
        api_key = ApiKey(
            account_id=account_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=request_body.name,
            status=ApiKeyStatus.ACTIVE
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        return CreateApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key_prefix=api_key.key_prefix,
            status=str(api_key.status),  # ApiKeyStatus is str, Enum so values are strings directly
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            key=full_key  # Only time full key is returned!
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR CREATING API KEY]")
