import logging
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.clients.stripe_client import get_payment_methods, attach_payment_method, create_stripe_customer, detach_payment_method
import stripe

from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

class AddPaymentMethodRequest(BaseModel):
    payment_method_id: str

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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
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
            raise handle_db_error(e, "[STRIPE ERROR RETRIEVING PAYMENT METHODS]")
            
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR RETRIEVING PAYMENT METHODS]")

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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Check if the account has a Stripe customer ID, create one if not
        if not account.stripe_customer_id:
            try:
                stripe_customer_id = create_stripe_customer(account.email)
                account.stripe_customer_id = stripe_customer_id
                db.commit()
                db.refresh(account)
                logger.info("Created Stripe customer %s for account %s", stripe_customer_id, account.id)
            except stripe.error.StripeError as e:
                logger.error("Failed to create Stripe customer: %s", e)
                db.rollback()
                raise handle_db_error(e, "[CREATE STRIPE CUSTOMER]")
        
        # Attach the payment method to the Stripe customer
        try:
            payment_method = attach_payment_method(
                account.stripe_customer_id,
                request_body.payment_method_id
            )
            
            return {
                "success": True,
                "payment_method": payment_method,
                "stripe_customer_id": account.stripe_customer_id,
                "message": "Payment method added successfully"
            }
        except stripe.error.StripeError as e:
            raise handle_db_error(e, "[STRIPE ERROR ATTACHING PAYMENT METHOD]")
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[AN ERROR OCCURRED WHILE ADDING PAYMENT METHOD]")

@router.delete("/payment-methods/{payment_method_id}")
@limiter.limit("10/minute")
async def delete_payment_method(
    payment_method_id: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Delete a payment method for the authenticated user.
    Verifies that the payment method belongs to the user's Stripe customer before deletion.
    """
    try:
        # Get the account from the database using the JWT account_id
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        # Check if the account has a Stripe customer ID
        if not account.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Stripe customer associated with this account"
            )
        
        # Verify the payment method belongs to this customer
        try:
            # Retrieve the payment method to verify it belongs to the customer
            payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
            
            # Check if the payment method is attached to this customer
            if payment_method.customer != account.stripe_customer_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Payment method does not belong to your account"
                )
            
            # Detach the payment method from the customer
            detach_payment_method(payment_method_id)
            
            return {
                "success": True,
                "message": "Payment method deleted successfully",
                "payment_method_id": payment_method_id
            }
            
        except stripe.error.InvalidRequestError as e:
            # Payment method not found or already detached
            if "No such payment_method" in str(e) or "already been detached" in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment method not found or already deleted"
                )
            raise handle_db_error(e, "[STRIPE INVALID PAYMENT METHOD]")
        except stripe.error.StripeError as e:
            raise handle_db_error(e, "[STRIPE ERROR DELETING PAYMENT METHOD]")
            
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[ERROR DELETING PAYMENT METHOD]")

