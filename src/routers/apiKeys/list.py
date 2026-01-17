"""
List API keys endpoint.
"""
from fastapi import APIRouter, Request
from typing import List
from src.deps import db_dependency, jwt_dependency
from src.db.models import ApiKey
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import ApiKeyResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.get("/", response_model=List[ApiKeyResponse])
@limiter.limit("30/minute")
async def list_api_keys(
    db: db_dependency,
    jwt: jwt_dependency,  # Must be logged in
    request: Request
):
    """
    List all API keys for the authenticated account.
    Only shows key prefix, never the full key.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        
        api_keys = db.query(ApiKey).filter(
            ApiKey.account_id == account_id
        ).order_by(ApiKey.created_at.desc()).all()
        
        return [
            ApiKeyResponse(
                id=key.id,
                name=key.name,
                key_prefix=key.key_prefix,
                status=str(key.status),  # ApiKeyStatus is str, Enum so values are strings directly
                created_at=key.created_at,
                last_used_at=key.last_used_at
            )
            for key in api_keys
        ]
        
    except Exception as e:
        print(f"Error listing API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing API keys: {str(e)}"
        )
