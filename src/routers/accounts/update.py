"""
Update account endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from slowapi import Limiter
from slowapi.util import get_remote_address
from .models import UpdateAccountRequest, AccountResponse

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.put("/me", response_model=AccountResponse)
@limiter.limit("10/minute")
async def update_account(
    request_body: UpdateAccountRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Update the authenticated user's account.
    
    Updatable fields:
    - email: The account email address
    - newsletter_subscribed: Newsletter subscription preference
    
    Note: Password changes should use the /auth/reset-password flow.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Check if at least one field is being updated
        if request_body.email is None and request_body.newsletter_subscribed is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field (email or newsletter_subscribed) must be provided for update"
            )
        
        # Update email if provided
        if request_body.email is not None:
            email = request_body.email.strip().lower()
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email cannot be empty"
                )
            
            # Check if email is already taken by another account
            existing_account = db.query(Account).filter(
                Account.email == email,
                Account.id != account_id
            ).first()
            
            if existing_account:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email address is already in use"
                )
            
            account.email = email
        
        # Update newsletter_subscribed if provided
        if request_body.newsletter_subscribed is not None:
            account.newsletter_subscribed = request_body.newsletter_subscribed
        
        # Commit the changes
        db.commit()
        db.refresh(account)
        
        return AccountResponse(
            id=account.id,
            email=account.email,
            newsletter_subscribed=account.newsletter_subscribed,
            stripe_customer_id=account.stripe_customer_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating account: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating account: {str(e)}"
        )
