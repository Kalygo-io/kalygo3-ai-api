"""
Pydantic models for the contacts router.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import date, datetime


# ── Contact models ────────────────────────────────────────────────────────────

class CreateContactRequest(BaseModel):
    first_name: str
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    email: str  # the default (primary) email — "Default email" in the UI
    alt_email_1: Optional[str] = None
    alt_email_2: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    # Social media profile URLs
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None


class UpdateContactRequest(BaseModel):
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    alt_email_1: Optional[str] = None
    alt_email_2: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    # Social media profile URLs
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None


class ContactEventResponse(BaseModel):
    id: int
    contact_id: int
    account_id: int
    event_type: str
    title: str
    description: Optional[str] = None
    occurred_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactResponse(BaseModel):
    id: int
    account_id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    name: str  # hybrid property: "{first_name} {middle_name} {last_name}".strip()
    email: str
    alt_email_1: Optional[str] = None
    alt_email_2: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[ContactEventResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ContactSummaryResponse(BaseModel):
    """Lightweight contact response without events (for list views)."""
    id: int
    account_id: int
    first_name: str
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    name: str  # hybrid property: "{first_name} {middle_name} {last_name}".strip()
    email: str
    alt_email_1: Optional[str] = None
    alt_email_2: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ContactListResponse(BaseModel):
    """Paginated envelope for the contacts list.

    Mirrors the established pagination contract used by the ingestion-logs
    endpoint ({items, total, limit, offset, has_more}) so the frontend
    pattern is consistent across the app.
    """
    contacts: List[ContactSummaryResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# ── Event models ──────────────────────────────────────────────────────────────

class CreateContactEventRequest(BaseModel):
    event_type: str
    title: str
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None


class UpdateContactEventRequest(BaseModel):
    event_type: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    occurred_at: Optional[datetime] = None


# ── Career Timeline models ────────────────────────────────────────────────────

class CreateCareerTimelineRequest(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None


class UpdateCareerTimelineRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class CareerTimelineResponse(BaseModel):
    id: int
    contact_id: int
    account_id: int
    title: str
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
