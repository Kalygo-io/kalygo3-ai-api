"""
Pydantic models for the companies router.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

from src.routers.contacts.models import ContactSummaryResponse


class CreateCompanyRequest(BaseModel):
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None


class UpdateCompanyRequest(BaseModel):
    name: Optional[str] = None
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None


class CompanyContactResponse(BaseModel):
    """A contact associated with a company, plus the join metadata."""
    id: int
    company_id: int
    contact_id: int
    account_id: int
    title: Optional[str] = None
    added_at: datetime
    contact: ContactSummaryResponse

    model_config = ConfigDict(from_attributes=True)


class CompanySummaryResponse(BaseModel):
    """Lightweight company response without contacts (for list views)."""
    id: int
    account_id: int
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None
    contact_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyResponse(BaseModel):
    """Full company response including associated contacts."""
    id: int
    account_id: int
    name: str
    domain: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    linkedin_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    contacts: List[CompanyContactResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CompanyListResponse(BaseModel):
    """Paginated envelope for the companies list.

    Mirrors the contacts list contract
    ({companies, total, limit, offset, has_more}) so the frontend
    pagination pattern stays consistent across the app.
    """
    companies: List[CompanySummaryResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AddContactToCompanyRequest(BaseModel):
    contact_id: int
    title: Optional[str] = None


class BulkAddContactsToCompanyRequest(BaseModel):
    contact_ids: List[int]
