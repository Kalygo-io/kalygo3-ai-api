from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel


class PendingToolApprovalResponse(BaseModel):
    id: int
    account_id: int
    agent_id: Optional[int]
    chat_session_id: Optional[int]
    tool_type: str
    status: str
    payload: Dict[str, Any]
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApproveToolApprovalResponse(BaseModel):
    id: int
    status: str
    message: str


class RejectToolApprovalResponse(BaseModel):
    id: int
    status: str
    message: str
