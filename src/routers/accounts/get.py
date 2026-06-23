"""
Get account details endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
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
