"""
Shared Pydantic models for the agents router.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class KnowledgeBase(BaseModel):
    provider: str
    index: str
    namespace: str
    description: Optional[str] = None


class CreateAgentRequest(BaseModel):
    name: str
    systemPrompt: str = Field(..., alias="systemPrompt", description="The system prompt for the agent")
    knowledgeBases: List[KnowledgeBase] = Field(..., alias="knowledgeBases", description="List of knowledge bases")
    
    class Config:
        populate_by_name = True  # Allow both camelCase and snake_case


class AgentResponse(BaseModel):
    id: int
    name: str
    system_prompt: Optional[str] = None
    config: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
