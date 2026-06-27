"""
Pydantic request/response models for access groups.
"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime


# ── Requests ──────────────────────────────────────────────────────────

class CreateAccessGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class UpdateAccessGroupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class AddMemberRequest(BaseModel):
    """Add a member by email address."""
    email: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        # Match how accounts are stored (lowercased + trimmed) so member
        # lookups don't silently miss on case/whitespace differences.
        return v.strip().lower()


class UpdateMemberRoleRequest(BaseModel):
    """Promote/demote a member. Owner only."""
    role: Literal["admin", "member"]


# ── Responses ─────────────────────────────────────────────────────────

class AccessGroupResponse(BaseModel):
    id: int
    name: str
    owner_account_id: int
    created_at: datetime
    updated_at: datetime
    member_count: Optional[int] = None
    # The viewer's relationship to this group: 'owner' | 'admin' | 'member'.
    # Lets the UI gate management controls without exposing account ids.
    my_role: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AccessGroupMemberResponse(BaseModel):
    id: int
    account_id: int
    email: str
    role: str  # 'admin' | 'member'
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GroupAgentResponse(BaseModel):
    """An agent that has been granted to the group."""
    agent_id: int
    agent_name: str
    granted_at: datetime

    model_config = ConfigDict(from_attributes=True)
