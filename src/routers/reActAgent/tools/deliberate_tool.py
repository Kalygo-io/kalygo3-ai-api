# tools/deliberate_tool.py
from __future__ import annotations
from typing import Optional

from langchain.tools.base import StructuredTool
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage


class DeliberateArgs(BaseModel):
    task: str = Field(..., description="One-sentence description of the objective.")
    context: Optional[str] = Field(None, description="Relevant facts/assumptions to consider.")
    n_options: int = Field(3, description="How many candidate plans to produce (2-5).")


async def deliberate_impl(task: str, context: Optional[str] = None, n_options: int = 3) -> str:
    # Validate n_options constraint manually since Pydantic v1 has issues with constraints in LangChain tools
    if n_options < 2 or n_options > 5:
        return f"Error: n_options must be between 2 and 5, got {n_options}"
    """
    One LLM call that returns MARKDOWN ONLY, with sections:
      ## Options
      ### Option 1: <Name>
      - Steps: ...
      - Pros: ...
      - Cons: ...
      - Estimated risk: 0–1
      - Estimated effort: 1–5
      (repeat for N options)
      ## Decision
      - Winner: <Name>
      - Rationale: <brief>
    """
    llm = ChatOpenAI(temperature=0, model="gpt-4o-mini").with_config(
        {"tags": ["deliberate_tool_llm", "markdown"]}
    )

    system = (
        "You are a careful strategist. Return MARKDOWN ONLY with exactly these sections:\n"
        "## Options\n"
        "### Option 1: <Name>\n- Steps: <comma-separated or short list>\n- Pros: <list>\n- Cons: <list>\n- Estimated risk: 0–1\n- Estimated effort: 1–5\n"
        "(Provide as many options as requested, numbered in order.)\n"
        "## Decision\n- Winner: <Name>\n- Rationale: <one short paragraph>\n"
        "No JSON. No code fences. No extra commentary."
    )
    user = (
        f"TASK: {task}\n"
        f"CONTEXT: {context or 'None'}\n"
        f"N_OPTIONS: {n_options}\n"
        "Produce the Markdown now."
    )

    resp = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content


deliberate_tool = StructuredTool(
    name="deliberate",
    description="Generate multiple candidate plans and choose the best one. Returns Markdown.",
    args_schema=DeliberateArgs,
    func=deliberate_impl,
    coroutine=deliberate_impl,
)
