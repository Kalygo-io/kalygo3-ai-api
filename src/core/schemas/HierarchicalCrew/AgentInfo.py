from pydantic import BaseModel, Field


class AgentInfo(BaseModel):
    role: str = Field(
        ...,
        description="Defines the agent’s function within the crew. It determines the kind of tasks the agent is best suited for.",
    )
    goal: str = Field(
        ...,
        description="The individual objective that the agent aims to achieve. It guides the agent’s decision-making process.",
    )
    backstory: str = Field(
        ...,
        description="Provides context to the agent’s role and goal, enriching the interaction and collaboration dynamics.",
    )