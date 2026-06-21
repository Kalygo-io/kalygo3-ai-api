"""
Pydantic models for the contact → companies sub-router (reverse of the
company → contacts association). Lets the contact detail view list, add, and
remove the companies a contact is associated with.

Kept in its own module (not contacts/models.py) to avoid a circular import:
companies.models already imports from contacts.models.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from src.routers.companies.models import CompanySummaryResponse


class AddCompanyToContactRequest(BaseModel):
    company_id: int
    title: Optional[str] = None


class ContactCompanyResponse(BaseModel):
    """A company a contact is associated with, plus the join metadata."""
    id: int
    company_id: int
    contact_id: int
    account_id: int
    title: Optional[str] = None
    added_at: datetime
    company: CompanySummaryResponse

    class Config:
        from_attributes = True
