from pydantic import BaseModel

class RunSwarmPrompt(BaseModel):
    content: str
    sessionId: str
    agentsConfig: list
    flow: str