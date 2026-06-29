"""
Pydantic request/response models for agent access grants.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator
from datetime import datetime


class CreateGrantRequest(BaseModel):
    """Share an agent with a group OR an individual (by email). Exactly one."""
    accessGroupId: Optional[int] = None
    granteeEmail: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one(self):
        if (self.accessGroupId is None) == (self.granteeEmail is None):
            raise ValueError("Provide exactly one of accessGroupId or granteeEmail")
        return self


class AgentAccessGrantResponse(BaseModel):
    id: int
    agent_id: int
    # Exactly one of these is set.
    access_group_id: Optional[int] = None
    grantee_account_id: Optional[int] = None
    label: str
    target_type: str  # 'group' | 'individual'
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
