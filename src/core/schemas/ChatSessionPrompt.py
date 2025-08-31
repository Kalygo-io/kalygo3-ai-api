from pydantic import BaseModel

class ChatSessionPrompt(BaseModel):
    prompt: str
    sessionId: str