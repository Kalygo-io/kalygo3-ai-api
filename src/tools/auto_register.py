"""
Auto-register all available tools.

This module automatically registers all tool builders with the ToolRegistry
when the tools package is imported.
"""
from .registry import register_tool_type
from .vector_search import create_vector_search_tool
from .vector_search_with_reranking import create_vector_search_with_reranking_tool


def register_all_tools():
    """Register all available tool types with the ToolRegistry."""
    # Register vector search tools
    register_tool_type("vectorSearch", create_vector_search_tool)
    register_tool_type("vectorSearchWithReranking", create_vector_search_with_reranking_tool)
    
    # Future tool types will be registered here:
    # register_tool_type("webSearch", create_web_search_tool)
    # register_tool_type("calculator", create_calculator_tool)
    # register_tool_type("apiCall", create_api_call_tool)
    # etc.
    
    print("[TOOL REGISTRY] All tool types registered")


# Auto-register on import
register_all_tools()
