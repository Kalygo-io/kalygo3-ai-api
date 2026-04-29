"""Pydantic models for the email_campaigns router."""
from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CreateEmailCampaignRequest(BaseModel):
    name: str = Field(max_length=255)
    description: Optional[str] = None
    email_template_id: Optional[int] = Field(
        default=None, description="FK to the email template used by this campaign")
    contact_list_id: Optional[int] = Field(
        default=None, description="FK to the contact list targeted by this campaign")
    status: Optional[str] = Field(
        default="draft", description="Campaign lifecycle status",
        pattern="^(draft|active|paused|completed)$")


class UpdateEmailCampaignRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    email_template_id: Optional[int] = None
    contact_list_id: Optional[int] = None
    status: Optional[str] = Field(
        default=None, pattern="^(draft|active|paused|completed)$")


class EmailCampaignResponse(BaseModel):
    id: int
    uuid: UUID
    account_id: int
    name: str
    description: Optional[str] = None
    email_template_id: Optional[int] = None
    contact_list_id: Optional[int] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
