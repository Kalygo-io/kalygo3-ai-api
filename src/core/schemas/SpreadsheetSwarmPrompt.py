from typing import Any, List
from pydantic import BaseModel

class SpreadsheetSwarmPrompt(BaseModel):
    content: str
    sessionId: str
    agentsConfig: List[Any]