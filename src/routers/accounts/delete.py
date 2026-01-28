"""
Delete account endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request, Response
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from slowapi import Limiter
from slowapi.util import get_remote_address
import os

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("5/minute")
async def delete_account(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    response: Response
):
    """
    Delete the authenticated user's account.
    
    This permanently deletes the account and all associated data.
    Related records (credentials, api_keys, leads) are cascade deleted.
    
    After deletion, the JWT cookie is cleared.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Delete the account (cascades to related records)
        db.delete(account)
        db.commit()
        
        # Clear the JWT cookie
        response.delete_cookie(
            key="jwt",
            domain=os.getenv("COOKIE_DOMAIN"),
            path="/"
        )
        
        return Response(status_code=status.HTTP_204_NO_CONTENT)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting account: {str(e)}"
        )
