"""
Revoke API key endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import ApiKey, ApiKeyStatus
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def revoke_api_key(
    key_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Revoke an API key. Only the owner can revoke.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.account_id == account_id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        api_key.status = ApiKeyStatus.REVOKED
        db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ERROR REVOKING API KEY]")
