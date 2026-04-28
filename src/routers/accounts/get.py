"""
Get account details endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from .models import AccountResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/me", response_model=AccountResponse)
@limiter.limit("30/minute")
async def get_account(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get the authenticated user's account details.
    Returns account info excluding sensitive fields (password, reset_token).
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        return AccountResponse(
            id=account.id,
            email=account.email,
            newsletter_subscribed=account.newsletter_subscribed,
            stripe_customer_id=account.stripe_customer_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING ACCOUNT]")
