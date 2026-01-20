"""
Tool System Usage Examples

This module demonstrates how to use the tool system programmatically.
These examples are for reference - in production, tools are created
automatically by the completion endpoint from agent configs.
"""
from typing import Dict, Any, List
from src.tools import (
    ToolRegistry,
    create_tool_from_config,
    create_tools_from_agent_config,
    register_tool_type,
)


async def example_1_list_available_tools():
    """Example 1: List all registered tool types."""
    print("=== Example 1: List Available Tools ===")
    
    # Get all registered tool types
    tool_types = ToolRegistry.list_types()
    print(f"Available tool types: {tool_types}")
    
    # Check if specific tool is registered
    is_registered = ToolRegistry.is_registered("vectorSearch")
    print(f"vectorSearch is registered: {is_registered}")
    
    # Get builder function for a tool type
    builder = ToolRegistry.get_builder("vectorSearch")
    print(f"Builder function: {builder}")
    print()


async def example_2_create_single_tool(account_id: int, db, auth_token: str):
    """Example 2: Create a single tool from config."""
    print("=== Example 2: Create Single Tool ===")
    
    tool_config = {
        "type": "vectorSearch",
        "provider": "pinecone",
        "index": "documentation",
        "namespace": "api-reference",
        "description": "Search API documentation and code examples",
        "topK": 15
    }
    
    # Create the tool
    tool = await create_tool_from_config(
        tool_config=tool_config,
        account_id=account_id,
        db=db,
        auth_token=auth_token
    )
    
    if tool:
        print(f"✓ Created tool: {tool.name}")
        print(f"  Description: {tool.description}")
        print(f"  Args schema: {tool.args_schema}")
        
        # Use the tool (example - in production this is called by the agent)
        result = await tool.arun(query="How do I authenticate?", top_k=5)
        print(f"  Example result: {result}")
    else:
        print("✗ Failed to create tool")
    
    print()


async def example_3_create_tools_from_v2_config(account_id: int, db, auth_token: str):
    """Example 3: Create tools from v2 agent config."""
    print("=== Example 3: Create Tools from v2 Config ===")
    
    agent_config = {
        "schema": "agent_config",
        "version": 2,
        "data": {
            "systemPrompt": "You are a helpful assistant with access to multiple knowledge bases.",
            "tools": [
                {
                    "type": "vectorSearch",
                    "provider": "pinecone",
                    "index": "products",
                    "namespace": "docs",
                    "description": "Product documentation and user guides",
                    "topK": 10
                },
                {
                    "type": "vectorSearch",
                    "provider": "pinecone",
                    "index": "support",
                    "namespace": "tickets",
                    "description": "Historical support tickets and solutions",
                    "topK": 5
                }
            ]
        }
    }
    
    # Create all tools
    tools = await create_tools_from_agent_config(
        agent_config=agent_config,
        account_id=account_id,
        db=db,
        auth_token=auth_token
    )
    
    print(f"✓ Created {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    
    print()


async def example_4_create_tools_from_v1_config(account_id: int, db, auth_token: str):
    """Example 4: Create tools from v1 agent config (backwards compatible)."""
    print("=== Example 4: Create Tools from v1 Config (Backwards Compatible) ===")
    
    # v1 config with knowledgeBases (legacy format)
    agent_config = {
        "schema": "agent_config",
        "version": 1,
        "data": {
            "systemPrompt": "You are a helpful assistant.",
            "knowledgeBases": [
                {
                    "provider": "pinecone",
                    "index": "legacy-docs",
                    "namespace": "user-manual",
                    "description": "Legacy user manual"
                }
            ]
        }
    }
    
    # Create tools - automatically converts v1 to v2 format
    tools = await create_tools_from_agent_config(
        agent_config=agent_config,
        account_id=account_id,
        db=db,
        auth_token=auth_token
    )
    
    print(f"✓ Created {len(tools)} tools from v1 config:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description}")
    
    print("ℹ️  v1 knowledgeBases automatically converted to v2 vectorSearch tools")
    print()


async def example_5_error_handling():
    """Example 5: Error handling."""
    print("=== Example 5: Error Handling ===")
    
    # Unknown tool type - returns None
    unknown_config = {
        "type": "unknownTool",
        "someParam": "value"
    }
    
    tool = await create_tool_from_config(
        tool_config=unknown_config,
        account_id=123,
        db=None,
        auth_token="test"
    )
    
    print(f"Unknown tool type result: {tool}")
    print("Expected: None (with warning logged)")
    print()
    
    # Missing required fields - returns None
    incomplete_config = {
        "type": "vectorSearch",
        "provider": "pinecone"
        # Missing: index, namespace
    }
    
    tool = await create_tool_from_config(
        tool_config=incomplete_config,
        account_id=123,
        db=None,
        auth_token="test"
    )
    
    print(f"Incomplete config result: {tool}")
    print("Expected: None (with error logged)")
    print()


def example_6_register_custom_tool():
    """Example 6: Register a custom tool type."""
    print("=== Example 6: Register Custom Tool ===")
    
    async def create_my_custom_tool(
        tool_config: Dict[str, Any],
        account_id: int,
        db: Any,
        auth_token: str = None,
        **kwargs
    ):
        """Custom tool builder."""
        from langchain_core.tools import StructuredTool
        from pydantic import BaseModel, Field
        
        async def my_tool_impl(input_text: str) -> Dict:
            """Tool implementation."""
            return {"result": f"Processed: {input_text}"}
        
        class MyToolArgs(BaseModel):
            input_text: str = Field(description="Text to process")
        
        return StructuredTool(
            func=my_tool_impl,
            coroutine=my_tool_impl,
            name="my_custom_tool",
            description="A custom tool",
            args_schema=MyToolArgs
        )
    
    # Register the custom tool
    register_tool_type("myCustomTool", create_my_custom_tool)
    
    print("✓ Registered custom tool type: myCustomTool")
    print(f"  Available tools: {ToolRegistry.list_types()}")
    print()


def example_7_tool_configs():
    """Example 7: Various tool configuration examples."""
    print("=== Example 7: Tool Configuration Examples ===")
    
    configs = {
        "Basic vector search": {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "docs",
            "namespace": "api"
        },
        
        "Vector search with description": {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "docs",
            "namespace": "api",
            "description": "API documentation with code examples"
        },
        
        "Vector search with custom topK": {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "docs",
            "namespace": "api",
            "topK": 20
        },
        
        "Vector search with re-ranking": {
            "type": "vectorSearchWithReranking",
            "provider": "pinecone",
            "index": "docs",
            "namespace": "support",
            "description": "Support documentation with re-ranking for best results",
            "topK": 20,
            "topN": 5
        },
        
        "Full vector search config": {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "knowledge-base",
            "namespace": "production-docs",
            "description": "Production documentation and best practices",
            "topK": 15
        },
        
        "Full vector search with re-ranking config": {
            "type": "vectorSearchWithReranking",
            "provider": "pinecone",
            "index": "premium-docs",
            "namespace": "enterprise",
            "description": "Enterprise documentation with highest quality results",
            "topK": 30,
            "topN": 8
        }
    }
    
    for name, config in configs.items():
        print(f"\n{name}:")
        import json
        print(json.dumps(config, indent=2))
    
    print()


def example_8_complete_agent_configs():
    """Example 8: Complete agent configuration examples."""
    print("=== Example 8: Complete Agent Configuration Examples ===")
    
    configs = {
        "Simple chat agent (no tools)": {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "You are a helpful assistant.",
                "tools": []
            }
        },
        
        "Single tool agent": {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "You are a documentation assistant.",
                "tools": [
                    {
                        "type": "vectorSearch",
                        "provider": "pinecone",
                        "index": "docs",
                        "namespace": "api-ref",
                        "description": "API documentation"
                    }
                ]
            }
        },
        
        "Multi-tool agent (fast search)": {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "You are a comprehensive support assistant.",
                "tools": [
                    {
                        "type": "vectorSearch",
                        "provider": "pinecone",
                        "index": "docs",
                        "namespace": "user-guides",
                        "description": "User guides and tutorials"
                    },
                    {
                        "type": "vectorSearch",
                        "provider": "pinecone",
                        "index": "support",
                        "namespace": "faq",
                        "description": "Frequently asked questions"
                    },
                    {
                        "type": "vectorSearch",
                        "provider": "pinecone",
                        "index": "tickets",
                        "namespace": "resolved",
                        "description": "Resolved support tickets"
                    }
                ]
            }
        },
        
        "Multi-tool agent (with re-ranking)": {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "You are a high-quality support assistant. Use re-ranking for best results.",
                "tools": [
                    {
                        "type": "vectorSearchWithReranking",
                        "provider": "pinecone",
                        "index": "docs",
                        "namespace": "user-guides",
                        "description": "User guides with re-ranking",
                        "topK": 20,
                        "topN": 5
                    },
                    {
                        "type": "vectorSearchWithReranking",
                        "provider": "pinecone",
                        "index": "support",
                        "namespace": "faq",
                        "description": "FAQ with re-ranking",
                        "topK": 15,
                        "topN": 3
                    }
                ]
            }
        },
        
        "Hybrid agent (both tool types)": {
            "schema": "agent_config",
            "version": 2,
            "data": {
                "systemPrompt": "You are a smart assistant. Use fast search for simple queries and re-ranked search for complex questions.",
                "tools": [
                    {
                        "type": "vectorSearch",
                        "provider": "pinecone",
                        "index": "docs",
                        "namespace": "quick-ref",
                        "description": "Quick reference guide for fast lookups",
                        "topK": 10
                    },
                    {
                        "type": "vectorSearchWithReranking",
                        "provider": "pinecone",
                        "index": "docs",
                        "namespace": "detailed",
                        "description": "Detailed documentation for complex queries",
                        "topK": 25,
                        "topN": 5
                    }
                ]
            }
        }
    }
    
    import json
    for name, config in configs.items():
        print(f"\n{name}:")
        print(json.dumps(config, indent=2))
    
    print()


async def run_all_examples(account_id: int = None, db = None, auth_token: str = None):
    """Run all examples."""
    print("\n" + "="*60)
    print("TOOL SYSTEM USAGE EXAMPLES")
    print("="*60 + "\n")
    
    # Examples that don't need DB/credentials
    await example_1_list_available_tools()
    example_6_register_custom_tool()
    example_7_tool_configs()
    example_8_complete_agent_configs()
    
    # Examples that need DB/credentials (skip if not provided)
    if account_id and db and auth_token:
        await example_2_create_single_tool(account_id, db, auth_token)
        await example_3_create_tools_from_v2_config(account_id, db, auth_token)
        await example_4_create_tools_from_v1_config(account_id, db, auth_token)
    else:
        print("ℹ️  Skipping examples 2-4 (require account_id, db, auth_token)")
        print()
    
    await example_5_error_handling()
    
    print("="*60)
    print("ALL EXAMPLES COMPLETED")
    print("="*60 + "\n")


if __name__ == "__main__":
    """
    Run examples standalone.
    
    Usage:
        python -m src.tools.examples
        
    Or import and run specific examples:
        from src.tools.examples import example_1_list_available_tools
        await example_1_list_available_tools()
    """
    import asyncio
    asyncio.run(run_all_examples())
