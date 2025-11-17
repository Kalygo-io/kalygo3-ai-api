from fastapi import APIRouter, HTTPException, Request, status
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from src.clients.stripe_client import get_payment_methods
import stripe

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


@router.get("/payment-methods")
@limiter.limit("30/minute")
async def get_user_payment_methods(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Retrieve all stored payment methods for the authenticated user.
    Returns payment methods associated with the user's Stripe customer ID.
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
        
        # Check if the account has a Stripe customer ID
        if not account.stripe_customer_id:
            return {
                "payment_methods": [],
                "message": "No Stripe customer associated with this account"
            }
        
        # Retrieve payment methods from Stripe
        try:
            payment_methods = get_payment_methods(account.stripe_customer_id)
            return {
                "payment_methods": payment_methods,
                "stripe_customer_id": account.stripe_customer_id
            }
        except stripe.error.StripeError as e:
            print(f"Stripe error retrieving payment methods: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to retrieve payment methods: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving payment methods: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving payment methods: {str(e)}"
        )

