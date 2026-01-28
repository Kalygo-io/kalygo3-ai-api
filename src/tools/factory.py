"""
Tool Factory

Creates tool instances from agent config definitions.
Supports both v1 (knowledgeBases) and v2 (tools) config formats.
"""
from typing import Dict, Any, List, Optional
from langchain_core.tools import StructuredTool
from .registry import ToolRegistry


async def create_tool_from_config(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Any,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create a tool from a v2 tool configuration.
    
    Args:
        tool_config: Tool configuration dict with 'type' field
        account_id: Account ID for fetching credentials
        db: Database session
        auth_token: Authentication token (JWT or API key)
        **kwargs: Additional context passed to tool builder
        
    Returns:
        StructuredTool instance or None if type not supported
        
    Example:
        tool_config = {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "my-index",
            "namespace": "docs",
            "topK": 10
        }
        tool = await create_tool_from_config(tool_config, account_id, db, auth_token)
    """
    tool_type = tool_config.get('type')
    
    if not tool_type:
        print(f"[TOOL FACTORY] Error: Tool config missing 'type' field: {tool_config}")
        return None
    
    # Get the builder for this tool type
    builder = ToolRegistry.get_builder(tool_type)
    
    if not builder:
        print(f"[TOOL FACTORY] Warning: Unknown tool type '{tool_type}'. Registered types: {ToolRegistry.list_types()}")
        return None
    
    # Call the builder
    try:
        print(f"[TOOL FACTORY] Creating tool of type: {tool_type}")
        tool = await builder(
            tool_config=tool_config,
            account_id=account_id,
            db=db,
            auth_token=auth_token,
            **kwargs
        )
        return tool
    except Exception as e:
        print(f"[TOOL FACTORY] Error creating tool of type '{tool_type}': {e}")
        import traceback
        traceback.print_exc()
        return None


async def create_tools_from_agent_config(
    agent_config: Dict[str, Any],
    account_id: int,
    db: Any,
    auth_token: Optional[str] = None,
    **kwargs
) -> List[StructuredTool]:
    """
    Create all tools from an agent configuration.
    
    Supports both v1 (knowledgeBases) and v2 (tools) config formats.
    
    Args:
        agent_config: Full agent config with 'version' and 'data'
        account_id: Account ID for fetching credentials
        db: Database session
        auth_token: Authentication token (JWT or API key)
        **kwargs: Additional context passed to tool builders
        
    Returns:
        List of StructuredTool instances
        
    Example:
        # v2 config
        agent_config = {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "...",
                "tools": [
                    {"type": "vectorSearch", "provider": "pinecone", ...},
                    {"type": "webSearch", "provider": "serper", ...}
                ]
            }
        }
        
        # v1 config (backwards compatible)
        agent_config = {
            "schema": "agent_config",
            "version": 1,
            "data": {
                "systemPrompt": "...",
                "knowledgeBases": [
                    {"provider": "pinecone", "index": "...", ...}
                ]
            }
        }
        
        tools = await create_tools_from_agent_config(agent_config, account_id, db, auth_token)
    """
    version = agent_config.get('version', 1)
    config_data = agent_config.get('data', {})
    tools = []
    
    print(f"[TOOL FACTORY] Creating tools from agent config v{version}")
    print(f"[TOOL FACTORY] Received kwargs: {list(kwargs.keys())}")
    
    if version == 1:
        # v1: knowledgeBases format
        knowledge_bases = config_data.get('knowledgeBases', [])
        print(f"[TOOL FACTORY] Found {len(knowledge_bases)} knowledge bases (v1 format)")
        
        # Convert each knowledge base to a vectorSearch tool config
        for kb in knowledge_bases:
            # Map v1 knowledge base to v2 vectorSearch tool
            tool_config = {
                "type": "vectorSearch",
                "provider": kb.get('provider'),
                "index": kb.get('index'),
                "namespace": kb.get('namespace'),
                "description": kb.get('description', f"Search the {kb.get('namespace')} knowledge base"),
                "topK": 10  # Default for v1 configs
            }
            
            tool = await create_tool_from_config(
                tool_config=tool_config,
                account_id=account_id,
                db=db,
                auth_token=auth_token,
                **kwargs
            )
            
            if tool:
                tools.append(tool)
    
    elif version == 2:
        # v2: tools format
        tool_configs = config_data.get('tools', [])
        print(f"[TOOL FACTORY] Found {len(tool_configs)} tools (v2 format)")
        
        for tool_config in tool_configs:
            tool = await create_tool_from_config(
                tool_config=tool_config,
                account_id=account_id,
                db=db,
                auth_token=auth_token,
                **kwargs
            )
            
            if tool:
                tools.append(tool)
    
    else:
        print(f"[TOOL FACTORY] Unsupported config version: {version}")
    
    print(f"[TOOL FACTORY] Created {len(tools)} tools successfully")
    return tools
