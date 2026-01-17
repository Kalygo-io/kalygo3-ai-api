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


class AgentResponse(BaseModel):
    id: int
    name: str
    config: Optional[Dict[str, Any]] = None
    
    # Extract systemPrompt from config for convenience
    @property
    def systemPrompt(self) -> Optional[str]:
        """Extract systemPrompt from config if available."""
        if self.config and isinstance(self.config, dict):
            data = self.config.get("data", {})
            if isinstance(data, dict):
                return data.get("systemPrompt")
        return None

    class Config:
        from_attributes = True
