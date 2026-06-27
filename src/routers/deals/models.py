"""
Pydantic models for the deals router.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime


class CreateDealRequest(BaseModel):
    title: str
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None  # defaults to "USD" server-side
    stage: Optional[str] = None     # defaults to "lead" server-side
    expected_close_date: Optional[date] = None
    closed_at: Optional[datetime] = None
    # Optional link to a contact. None => account-level deal not yet tied
    # to a person.
    contact_id: Optional[int] = None


class UpdateDealRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    stage: Optional[str] = None
    expected_close_date: Optional[date] = None
    closed_at: Optional[datetime] = None
    contact_id: Optional[int] = None


class DealResponse(BaseModel):
    id: int
    account_id: int
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None  # from Deal.contact (eager-loaded)
    title: str
    description: Optional[str] = None
    amount: Optional[float] = None
    currency: str
    stage: str
    expected_close_date: Optional[date] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealListResponse(BaseModel):
    """Paginated envelope for the deals list.

    Mirrors the contacts list contract
    ({items, total, limit, offset, has_more}) so the frontend pagination
    pattern stays consistent across the app.
    """
    deals: List[DealResponse]
    total: int
    limit: int
    offset: int
    has_more: bool
