"""
Tool call formatting helpers for agent completion.

Handles formatting tool call data according to the chat_message.v2.json schema.
"""
from typing import Dict, Any, Optional, List


def format_tool_call(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Any
) -> Optional[Dict[str, Any]]:
    """
    Format a tool call according to the chat_message.v2.json schema.
    
    Determines the tool type from the tool name and formats the input/output
    appropriately for each tool type.
    
    Args:
        tool_name: The name of the tool that was executed
        tool_input: The input that was passed to the tool
        tool_output: The output returned by the tool
        
    Returns:
        Formatted tool call dict, or None if the tool output is invalid
    """
    # Validate tool_output is a dict
    if not isinstance(tool_output, dict):
        print(f"[TOOL CALLS] Warning: tool_output is not a dict (type: {type(tool_output)})")
        return None
    
    # Determine tool type and format accordingly
    if tool_name.startswith("search_rerank_"):
        return _format_vector_search_rerank(tool_name, tool_input, tool_output)
    elif tool_name.startswith("search_"):
        return _format_vector_search(tool_name, tool_input, tool_output)
    elif tool_name.startswith("query_"):
        return _format_db_table_read(tool_name, tool_input, tool_output)
    elif tool_name.startswith("insert_") or tool_name.startswith("create_"):
        return _format_db_table_write(tool_name, tool_input, tool_output)
    else:
        # Generic tool format for unknown tool types
        return _format_generic_tool(tool_name, tool_input, tool_output)


def _format_vector_search(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Format vector search tool call."""
    results = _format_search_results(tool_output.get('results', []))
    
    return {
        "toolType": "vectorSearch",
        "toolName": tool_name,
        "input": {
            "query": tool_input.get('query', ''),
            "topK": tool_input.get('top_k', tool_input.get('topK'))
        },
        "output": {
            "results": results,
            "namespace": tool_output.get('namespace', ''),
            "index": tool_output.get('index', '')
        }
    }


def _format_vector_search_rerank(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Format vector search with reranking tool call."""
    results = _format_search_results(tool_output.get('results', []))
    
    return {
        "toolType": "vectorSearchWithReranking",
        "toolName": tool_name,
        "input": {
            "query": tool_input.get('query', ''),
            "topK": tool_input.get('top_k', tool_input.get('topK'))
        },
        "output": {
            "results": results,
            "namespace": tool_output.get('namespace', ''),
            "index": tool_output.get('index', '')
        }
    }


def _format_search_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format search results according to v2 schema."""
    formatted = []
    for result in results:
        formatted.append({
            "id": result.get("id", ""),
            "score": result.get("score", 0.0),
            "metadata": result.get("metadata", {})
        })
    return formatted


def _format_db_table_read(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Format database table read tool call."""
    return {
        "toolType": "dbTableRead",
        "toolName": tool_name,
        "input": {
            "filters": tool_input.get('filters'),
            "limit": tool_input.get('limit'),
            "offset": tool_input.get('offset')
        },
        "output": {
            "results": tool_output.get('results', []),
            "table": tool_output.get('table', ''),
            "count": tool_output.get('count', 0)
        }
    }


def _format_db_table_write(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Format database table write tool call."""
    return {
        "toolType": "dbTableWrite",
        "toolName": tool_name,
        "input": {
            "data": tool_input  # The flat input IS the data
        },
        "output": {
            "success": tool_output.get('success', False),
            "table": tool_output.get('table', ''),
            "inserted": tool_output.get('inserted', {}),
            "message": tool_output.get('message', ''),
            "error": tool_output.get('error')
        }
    }


def _format_generic_tool(
    tool_name: str,
    tool_input: Dict[str, Any],
    tool_output: Dict[str, Any]
) -> Dict[str, Any]:
    """Format generic/unknown tool call."""
    return {
        "toolType": "custom",
        "toolName": tool_name,
        "input": tool_input,
        "output": tool_output
    }
