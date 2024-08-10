from langchain.tools.base import StructuredTool
from langchain_community.utilities import GoogleSerperAPIWrapper
from langchain_core.pydantic_v1 import BaseModel, Field

class SearchQuery(BaseModel):
    query: str = Field()
    pass

search = GoogleSerperAPIWrapper()

serp_tool = StructuredTool(
    name="serp_tool",
    description="A tool for searching the web for information.",
    func=search.run,
    args_schema=SearchQuery,
)