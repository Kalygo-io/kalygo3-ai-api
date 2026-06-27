"""
Pydantic models for API key endpoints.
"""
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class CreateApiKeyRequest(BaseModel):
    name: Optional[str] = None  # Optional friendly name


class ApiKeyResponse(BaseModel):
    id: int
    name: Optional[str]
    key_prefix: str  # e.g., "kalygo_live_abc123..."
    status: str
    created_at: datetime
    last_used_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class CreateApiKeyResponse(ApiKeyResponse):
    key: str  # Full key - only in create response!
