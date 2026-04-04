"""
Pydantic models for the email_events router.
"""
from pydantic import BaseModel
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime

EmailEventType = Literal["send", "delivery", "open", "bounce", "complaint", "other"]


class CreateEmailEventRequest(BaseModel):
    email_address: str
    event_type: EmailEventType
    tool_approval_id: Optional[int] = None
    campaign_id: Optional[int] = None
    contact_id: Optional[int] = None
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None


class BulkCreateEmailEventsRequest(BaseModel):
    events: List[CreateEmailEventRequest]


class UpdateEmailEventRequest(BaseModel):
    """Only event_metadata is mutable after creation."""
    event_metadata: Optional[Dict[str, Any]] = None


class EmailEventResponse(BaseModel):
    id: int
    account_id: int
    tool_approval_id: Optional[int] = None
    campaign_id: Optional[int] = None
    contact_id: Optional[int] = None
    email_address: str
    event_type: str
    provider: Optional[str] = None
    provider_message_id: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EmailEventStatsResponse(BaseModel):
    """Aggregated counts per event_type — useful for dashboard summary cards."""
    send: int = 0
    delivery: int = 0
    open: int = 0
    bounce: int = 0
    complaint: int = 0
    other: int = 0
    total: int = 0
