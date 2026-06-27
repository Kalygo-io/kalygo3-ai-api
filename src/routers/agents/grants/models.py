"""
Pydantic request/response models for agent access grants.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class CreateGrantRequest(BaseModel):
    accessGroupId: int


class AgentAccessGrantResponse(BaseModel):
    id: int
    agent_id: int
    access_group_id: int
    access_group_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
