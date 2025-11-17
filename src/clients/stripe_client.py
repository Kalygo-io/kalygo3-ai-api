import stripe
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize Stripe with API key from environment
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
        customer = stripe.Customer.create(
            email=email,
        )
        return customer.id
    except stripe.error.StripeError as e:
        print(f"Stripe error creating customer: {str(e)}")
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
        # List all payment methods for the customer
        payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type='card'
        )
        
        # Format the payment methods to return only relevant information
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
    except stripe.error.StripeError as e:
        print(f"Stripe error retrieving payment methods: {str(e)}")
        raise

