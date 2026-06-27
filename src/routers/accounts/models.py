"""
Shared Pydantic models for the accounts router.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional


class AccountResponse(BaseModel):
    """Response model for account data (excludes sensitive fields)."""
    id: int
    email: str
    newsletter_subscribed: bool
    stripe_customer_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateAccountRequest(BaseModel):
    """Request model for updating account fields."""
    email: Optional[str] = None
    newsletter_subscribed: Optional[bool] = None

    model_config = ConfigDict(populate_by_name=True)
