"""
Server-Sent Events (SSE) helpers for agent completion.

Provides consistent formatting for SSE events sent to the client.
"""
import json
from typing import Any, Optional, List, Dict


def sse_event(
    event: str,
    data: Optional[Any] = None,
    tool_calls: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Create a JSON-encoded SSE event.
    
    Args:
        event: The event type (e.g., "on_chain_start", "on_chat_model_stream")
        data: Optional data payload for the event
        tool_calls: Optional list of tool calls to include
        
    Returns:
        JSON string ready to be yielded in a StreamingResponse
    """
    payload: Dict[str, Any] = {"event": event}
    
    if data is not None:
        payload["data"] = data
    
    if tool_calls is not None:
        payload["toolCalls"] = tool_calls
    
    return json.dumps(payload, separators=(',', ':'))


def sse_error(error: str, message: str) -> str:
    """
    Create a JSON-encoded SSE error event.
    
    Args:
        error: Short error type/code
        message: Human-readable error message
        
    Returns:
        JSON string for an error event
    """
    return json.dumps({
        "event": "error",
        "data": {
            "error": error,
            "message": message
        }
    }, separators=(',', ':'))


# Common event types as constants for consistency
class EventType:
    """SSE event type constants."""
    CHAIN_START = "on_chain_start"
    CHAIN_END = "on_chain_end"
    CHAT_MODEL_START = "on_chat_model_start"
    CHAT_MODEL_STREAM = "on_chat_model_stream"
    CHAT_MODEL_END = "on_chat_model_end"
    TOOL_START = "on_tool_start"
    TOOL_END = "on_tool_end"
    ERROR = "error"
