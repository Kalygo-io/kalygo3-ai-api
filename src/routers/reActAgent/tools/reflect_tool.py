# tools/reflect_tool.py
from __future__ import annotations
from typing import Optional

from langchain.tools.base import StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


class ReflectArgs(BaseModel):
    task: str = Field(..., description="What are we trying to produce or decide?")
    working: str = Field(..., description="The current draft/plan/answer to critique.")
    goals: Optional[str] = Field(None, description="Constraints or acceptance criteria (optional).")


async def reflect_impl(task: str, working: str, goals: Optional[str] = None) -> str:
    """
    One LLM call that returns MARKDOWN ONLY, with sections:
      ## Critique  (3–6 bullets)
      ## Improvements  (numbered list)
      ## Confidence  (single value 0–1)
    """
    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini").with_config(
        {"tags": ["reflect_tool_llm", "markdown"]}
    )

    system = (
        "You are a concise reviewer. Return MARKDOWN ONLY with exactly these sections:\n"
        "## Critique\n- bullet 1\n- bullet 2\n...\n"
        "## Improvements\n1. edit one\n2. edit two\n...\n"
        "## Confidence\n0.00–1.00\n"
        "No JSON. No code fences. No extra commentary."
    )
    user = (
        f"TASK: {task}\n"
        f"GOALS/CONSTRAINTS: {goals or 'None'}\n"
        "CURRENT:\n---\n"
        f"{working}\n"
        "---\n"
        "Produce the Markdown now."
    )

    resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content


reflect_tool = StructuredTool(
    name="reflect",
    description="Critique a working draft/plan and suggest prioritized improvements. Returns Markdown.",
    args_schema=ReflectArgs,
    func=reflect_impl,
    coroutine=reflect_impl,
)
