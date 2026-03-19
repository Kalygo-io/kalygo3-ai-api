"""
Pydantic models for the contacts router.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


# ── Contact models ────────────────────────────────────────────────────────────

class CreateContactRequest(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class UpdateContactRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class ContactEventResponse(BaseModel):
    id: int
    contact_id: int
    account_id: int
    event_type: str
    title: str
    description: Optional[str] = None
    occurred_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ContactResponse(BaseModel):
    id: int
    account_id: int
    first_name: str
    last_name: Optional[str] = None
    name: str  # hybrid property: "{first_name} {last_name}".strip()
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    events: List[ContactEventResponse] = []

    class Config:
        from_attributes = True


class ContactSummaryResponse(BaseModel):
    """Lightweight contact response without events (for list views)."""
    id: int
    account_id: int
    first_name: str
    last_name: Optional[str] = None
    name: str  # hybrid property: "{first_name} {last_name}".strip()
    email: str
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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
