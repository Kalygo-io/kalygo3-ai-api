"""
Pydantic models for the prompts router.
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CreatePromptRequest(BaseModel):
    """Request body for creating a new prompt."""
    name: str
    description: Optional[str] = None
    content: str


class UpdatePromptRequest(BaseModel):
    """Request body for updating an existing prompt."""
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class PromptResponse(BaseModel):
    """Response model for a prompt."""
    id: int
    account_id: int
    name: str
    description: Optional[str] = None
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
