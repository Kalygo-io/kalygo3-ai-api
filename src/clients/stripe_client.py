import logging
import stripe
import os

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def create_stripe_customer(email: str) -> str:
    """
    Create a Stripe customer and return the customer ID.
    
    Args:
        email: The email address for the customer
        
    Returns:
        The Stripe customer ID (e.g., 'cus_xxxxx')
        
    Raises:
        stripe.error.StripeError: If Stripe API call fails
    """
    try:
        customer = stripe.Customer.create(email=email)
        return customer.id
    except stripe.error.StripeError:
        logger.exception("Stripe error creating customer for %s", email)
        raise


def get_payment_methods(customer_id: str) -> list:
    """
    Retrieve all payment methods for a Stripe customer.
    
    Args:
        customer_id: The Stripe customer ID (e.g., 'cus_xxxxx')
        
    Returns:
        List of payment method dictionaries with relevant information
        
    Raises:
        stripe.error.StripeError: If Stripe API call fails
    """
    try:
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card'
        )
        
        formatted_methods = []
        for pm in payment_methods.data:
            formatted_methods.append({
                "id": pm.id,
                "type": pm.type,
                "card": {
                    "brand": pm.card.brand if pm.card else None,
                    "last4": pm.card.last4 if pm.card else None,
                    "exp_month": pm.card.exp_month if pm.card else None,
                    "exp_year": pm.card.exp_year if pm.card else None,
                } if pm.card else None,
                "created": pm.created,
            })
        
        return formatted_methods
    except stripe.error.StripeError:
        logger.exception("Stripe error retrieving payment methods for %s", customer_id)
        raise


def attach_payment_method(customer_id: str, payment_method_id: str) -> dict:
    """
    Attach a payment method to a Stripe customer.
    
    Args:
        customer_id: The Stripe customer ID (e.g., 'cus_xxxxx')
        payment_method_id: The Stripe payment method ID (e.g., 'pm_xxxxx')
        
    Returns:
        Dictionary with payment method information
        
    Raises:
        stripe.error.StripeError: If Stripe API call fails
    """
    try:
        payment_method = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
        )
        
        return {
            "id": payment_method.id,
            "type": payment_method.type,
            "card": {
                "brand": payment_method.card.brand if payment_method.card else None,
                "last4": payment_method.card.last4 if payment_method.card else None,
                "exp_month": payment_method.card.exp_month if payment_method.card else None,
                "exp_year": payment_method.card.exp_year if payment_method.card else None,
            } if payment_method.card else None,
            "created": payment_method.created,
        }
    except stripe.error.StripeError:
        logger.exception("Stripe error attaching payment method %s to %s", payment_method_id, customer_id)
        raise


def create_payment_method_from_card(
    card_number: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    cardholder_name: str = None,
    billing_zip: str = None
) -> dict:
    """
    Create a Stripe payment method from card details.
    
    Args:
        card_number: The card number (without spaces)
        exp_month: Expiration month (1-12)
        exp_year: Expiration year (4 digits)
        cvv: Card security code
        cardholder_name: Name on the card (optional)
        billing_zip: Billing ZIP code (optional)
        
    Returns:
        Dictionary with payment method information including the payment method ID
        
    Raises:
        stripe.error.StripeError: If Stripe API call fails
    """
    try:
        payment_method_data = {
            "type": "card",
            "card": {
                "number": card_number,
                "exp_month": exp_month,
                "exp_year": exp_year,
                "cvc": cvv,
            }
        }
        
        billing_details = {}
        if cardholder_name:
            billing_details["name"] = cardholder_name
        if billing_zip:
            billing_details["address"] = {"postal_code": billing_zip}
        
        if billing_details:
            payment_method_data["billing_details"] = billing_details
        
        payment_method = stripe.PaymentMethod.create(**payment_method_data)
        
        return {
            "id": payment_method.id,
            "type": payment_method.type,
            "card": {
                "brand": payment_method.card.brand if payment_method.card else None,
                "last4": payment_method.card.last4 if payment_method.card else None,
                "exp_month": payment_method.card.exp_month if payment_method.card else None,
                "exp_year": payment_method.card.exp_year if payment_method.card else None,
            } if payment_method.card else None,
            "created": payment_method.created,
        }
    except stripe.error.StripeError:
        logger.exception("Stripe error creating payment method")
        raise


def detach_payment_method(payment_method_id: str) -> bool:
    """
    Detach a payment method from a customer.
    
    Args:
        payment_method_id: The Stripe payment method ID (e.g., 'pm_xxxxx')
        
    Returns:
        True if successful
        
    Raises:
        stripe.error.StripeError: If Stripe API call fails
    """
    try:
        stripe.PaymentMethod.detach(payment_method_id)
        return True
    except stripe.error.StripeError:
        logger.exception("Stripe error detaching payment method %s", payment_method_id)
        raise
