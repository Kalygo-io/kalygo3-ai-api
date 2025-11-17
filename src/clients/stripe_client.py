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

