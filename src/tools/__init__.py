"""
Agent Tools System

This module provides a registry and factory pattern for creating tools
that can be used by agents. Tools extend agent capabilities with actions
like vector search, web search, calculations, API calls, etc.

Tool types are automatically registered when this package is imported.
"""

from .factory import create_tool_from_config, create_tools_from_agent_config
from .registry import ToolRegistry, register_tool_type, get_tool_builder

# Import auto_register to register all available tools
from . import auto_register  # noqa: F401

__all__ = [
    'create_tool_from_config',
    'create_tools_from_agent_config',
    'ToolRegistry',
    'register_tool_type',
    'get_tool_builder',
]
