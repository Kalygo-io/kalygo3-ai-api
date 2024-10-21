from typing import List
from pydantic import BaseModel, Field

from src.core.schemas.HierarchicalCrew.AgentInfo import AgentInfo

class CrewLevel(BaseModel):
    crew_name: str = Field(
        ...,
        description="The name of the swarm.",
    )
    managerAgent: AgentInfo = Field(
        ...,
        description="The manager agent is the agent that will be responsible for managing the crew and ensuring that the task is completed.",
    )
    workerAgents: List[AgentInfo] = Field(
        ...,
        description="A list of agents that are part of the crew.",
    )
    