"""
Shared Pydantic models for the agents router.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class KnowledgeBase(BaseModel):
    provider: str
    index: str
    namespace: str
    description: Optional[str] = None


class CreateAgentRequest(BaseModel):
    name: str
    description: Optional[str] = None
    knowledge_bases: Optional[List[KnowledgeBase]] = None


class AgentResponse(BaseModel):
    id: int
    name: str
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
