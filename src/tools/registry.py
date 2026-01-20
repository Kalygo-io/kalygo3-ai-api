"""
Tool Registry

Manages available tool types and their builders.
"""
from typing import Dict, Callable, Any, Optional
from langchain_core.tools import StructuredTool


# Type alias for tool builder functions
ToolBuilder = Callable[..., StructuredTool]

class ToolRegistry:
    """Registry for tool builders by tool type."""
    
    _builders: Dict[str, ToolBuilder] = {}
    
    @classmethod
    def register(cls, tool_type: str, builder: ToolBuilder) -> None:
        """
        Register a tool builder for a specific tool type.
        
        Args:
            tool_type: The tool type identifier (e.g., "vectorSearch")
            builder: Async function that creates a StructuredTool from config
        """
        cls._builders[tool_type] = builder
        print(f"[TOOL REGISTRY] Registered tool type: {tool_type}")
    
    @classmethod
    def get_builder(cls, tool_type: str) -> Optional[ToolBuilder]:
        """
        Get the builder function for a tool type.
        
        Args:
            tool_type: The tool type identifier
            
        Returns:
            Builder function or None if not found
        """
        return cls._builders.get(tool_type)
    
    @classmethod
    def list_types(cls) -> list[str]:
        """
        List all registered tool types.
        
        Returns:
            List of tool type identifiers
        """
        return list(cls._builders.keys())
    
    @classmethod
    def is_registered(cls, tool_type: str) -> bool:
        """
        Check if a tool type is registered.
        
        Args:
            tool_type: The tool type identifier
            
        Returns:
            True if registered, False otherwise
        """
        return tool_type in cls._builders


# Convenience functions
def register_tool_type(tool_type: str, builder: ToolBuilder) -> None:
    """Register a tool builder."""
    ToolRegistry.register(tool_type, builder)


def get_tool_builder(tool_type: str) -> Optional[ToolBuilder]:
    """Get a tool builder by type."""
    return ToolRegistry.get_builder(tool_type)
