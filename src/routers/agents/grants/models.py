"""
Pydantic request/response models for agent access grants.
"""
from pydantic import BaseModel
from datetime import datetime


class CreateGrantRequest(BaseModel):
    accessGroupId: int


class AgentAccessGrantResponse(BaseModel):
    id: int
    agent_id: int
    access_group_id: int
    access_group_name: str
    created_at: datetime

    class Config:
        from_attributes = True
