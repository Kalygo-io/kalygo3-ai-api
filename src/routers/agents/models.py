"""
Shared Pydantic models for the agents router.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any


class CreateAgentRequest(BaseModel):
    name: str
    config: Dict[str, Any]
    
    class Config:
        populate_by_name = True


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    
    class Config:
        populate_by_name = True


class AgentResponse(BaseModel):
    id: int
    name: str
    config: Optional[Dict[str, Any]] = None
    is_owner: Optional[bool] = None

    class Config:
        from_attributes = True
