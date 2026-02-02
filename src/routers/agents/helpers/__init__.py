"""
Agent completion helpers.

This module contains refactored helper functions for the agent completion endpoint.
"""
from .message_history import (
    build_message_history,
    store_user_message,
    store_ai_message,
)
from .auth import extract_auth_token
from .tool_calls import format_tool_call
from .sse_events import sse_event, sse_error

__all__ = [
    # Message history
    "build_message_history",
    "store_user_message", 
    "store_ai_message",
    # Auth
    "extract_auth_token",
    # Tool calls
    "format_tool_call",
    # SSE events
    "sse_event",
    "sse_error",
]
