"""
Pydantic models for the contact_lists router.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from src.routers.contacts.models import ContactSummaryResponse


class CreateContactListRequest(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateContactListRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ContactListMemberResponse(BaseModel):
    id: int
    contact_list_id: int
    contact_id: int
    account_id: int
    added_at: datetime
    contact: ContactSummaryResponse

    class Config:
        from_attributes = True


class ContactListSummaryResponse(BaseModel):
    """Lightweight list response without members (for list views)."""
    id: int
    account_id: int
    name: str
    description: Optional[str] = None
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Full list response including member contacts."""
    id: int
    account_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    members: List[ContactListMemberResponse] = []

    class Config:
        from_attributes = True


class AddContactToListRequest(BaseModel):
    contact_id: int


class BulkAddContactsToListRequest(BaseModel):
    contact_ids: List[int]
