"""
Pydantic request/response models for access groups.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Requests ──────────────────────────────────────────────────────────

class CreateAccessGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class UpdateAccessGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AddMemberRequest(BaseModel):
    """Add a member by email address."""
    email: str = Field(..., min_length=1)


# ── Responses ─────────────────────────────────────────────────────────

class AccessGroupResponse(BaseModel):
    id: int
    name: str
    owner_account_id: int
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = None

    class Config:
        from_attributes = True


class AccessGroupMemberResponse(BaseModel):
    id: int
    account_id: int
    email: str
    created_at: datetime

    class Config:
        from_attributes = True
