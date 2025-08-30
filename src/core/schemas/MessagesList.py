from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class Message(BaseModel):
    role: str  # "user", "ai", "system", "tool", "tool_result", etc.
    content: str
    timestamp: Optional[datetime] = None

class MessagesList(BaseModel):
    messages: List[Message]