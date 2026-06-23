"""
Delete account endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request, Response
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
import os
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
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
        raise handle_db_error(e, "[ERROR DELETING ACCOUNT]")
