from pydantic import BaseModel

class RunCrewPrompt(BaseModel):
    content: str
    sessionId: str
    crewConfig: dict