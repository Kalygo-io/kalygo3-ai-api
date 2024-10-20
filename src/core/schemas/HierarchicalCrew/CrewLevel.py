from typing import List
from pydantic import BaseModel, Field

from src.core.schemas.DesignAndRunSwarm.AgentInfo import AgentInfo

class CrewLevel(BaseModel):
    crew_name: str = Field(
        ...,
        description="The name of the swarm.",
    )
    task: str = Field(
        ...,
        description="The task that the user wants the swarm to complete. This is the task that the user wants the agents to complete. Make it very specific and clear.",
    )
    agents: List[AgentInfo] = Field(
        ...,
        description="A list of agents that are part of the crew.",
    )
    