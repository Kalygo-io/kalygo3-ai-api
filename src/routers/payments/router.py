from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional
from src.deps import db_dependency, jwt_dependency
from src.db.models import Account
from src.clients.stripe_client import get_payment_methods, attach_payment_method, create_stripe_customer, create_payment_method_from_card
import stripe

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


class AddPaymentMethodRequest(BaseModel):
    payment_method_id: str


class CreatePaymentMethodRequest(BaseModel):
    card_number: str
    exp_month: int
    exp_year: int
    cvv: str
    cardholder_name: Optional[str] = None
    billing_zip: Optional[str] = None


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


@router.post("/payment-methods")
@limiter.limit("10/minute")
async def add_payment_method(
    request_body: AddPaymentMethodRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Add a payment method to the authenticated user's Stripe customer.
    If the user doesn't have a Stripe customer ID, creates one first.
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
        
        # Check if the account has a Stripe customer ID, create one if not
        if not account.stripe_customer_id:
            try:
                stripe_customer_id = create_stripe_customer(account.email)
                account.stripe_customer_id = stripe_customer_id
                db.commit()
                db.refresh(account)
                print(f"Created Stripe customer: {stripe_customer_id} for account: {account.id}")
            except stripe.error.StripeError as e:
                print(f"Failed to create Stripe customer: {str(e)}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create Stripe customer: {str(e)}"
                )
        
        # Attach the payment method to the Stripe customer
        try:
            payment_method = attach_payment_method(
                account.stripe_customer_id,
                request_body.payment_method_id
            )
            print(f"Attached payment method {request_body.payment_method_id} to customer {account.stripe_customer_id}")
            
            return {
                "success": True,
                "payment_method": payment_method,
                "stripe_customer_id": account.stripe_customer_id,
                "message": "Payment method added successfully"
            }
        except stripe.error.StripeError as e:
            print(f"Stripe error attaching payment method: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to add payment method: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error adding payment method: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while adding payment method: {str(e)}"
        )


@router.post("/create-payment-method")
@limiter.limit("10/minute")
async def create_payment_method(
    request_body: CreatePaymentMethodRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a payment method from card details and attach it to the authenticated user's Stripe customer.
    If the user doesn't have a Stripe customer ID, creates one first.
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
        
        # Check if the account has a Stripe customer ID, create one if not
        if not account.stripe_customer_id:
            try:
                stripe_customer_id = create_stripe_customer(account.email)
                account.stripe_customer_id = stripe_customer_id
                db.commit()
                db.refresh(account)
                print(f"Created Stripe customer: {stripe_customer_id} for account: {account.id}")
            except stripe.error.StripeError as e:
                print(f"Failed to create Stripe customer: {str(e)}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create Stripe customer: {str(e)}"
                )
        
        # Create payment method from card details
        try:
            payment_method = create_payment_method_from_card(
                card_number=request_body.card_number,
                exp_month=request_body.exp_month,
                exp_year=request_body.exp_year,
                cvv=request_body.cvv,
                cardholder_name=request_body.cardholder_name,
                billing_zip=request_body.billing_zip
            )
            
            # Attach the payment method to the Stripe customer
            attach_payment_method(
                account.stripe_customer_id,
                payment_method["id"]
            )
            
            print(f"Created and attached payment method {payment_method['id']} to customer {account.stripe_customer_id}")
            
            return {
                "success": True,
                "payment_method": payment_method,
                "stripe_customer_id": account.stripe_customer_id,
                "message": "Payment method created and added successfully"
            }
        except stripe.error.CardError as e:
            # Card-specific errors (e.g., card declined, invalid card number)
            print(f"Stripe card error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Card error: {e.user_message if hasattr(e, 'user_message') else str(e)}"
            )
        except stripe.error.StripeError as e:
            print(f"Stripe error creating payment method: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create payment method: {str(e)}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating payment method: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating payment method: {str(e)}"
        )

