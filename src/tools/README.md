# Agent Tools System

Centralized tool registry and factory for agent capabilities.

## Overview

The tools system provides a clean, extensible way to add new capabilities to agents. Tools are registered in a central registry and created dynamically from agent configurations.

## Architecture

```
src/tools/
├── __init__.py           # Package entry point, exports main functions
├── registry.py           # Tool registry for managing tool types
├── factory.py            # Tool factory for creating tools from configs
├── auto_register.py      # Auto-registers all available tools
├── vector_search.py      # Vector search tool implementation
└── README.md            # This file
```

### Key Components

1. **Tool Registry** (`registry.py`)
   - Manages available tool types
   - Maps tool type strings to builder functions
   - Thread-safe singleton pattern

2. **Tool Factory** (`factory.py`)
   - Creates tool instances from configs
   - Supports both v1 and v2 config formats
   - Handles errors gracefully

3. **Tool Implementations** (e.g., `vector_search.py`)
   - Individual tool builders
   - Async functions that return `StructuredTool` instances
   - Self-contained with all dependencies

4. **Auto-Registration** (`auto_register.py`)
   - Automatically registers tools on package import
   - Centralized registration point for all tools

## Usage

### Creating Tools from Agent Config

```python
from src.tools import create_tools_from_agent_config

# v2 config
agent_config = {
    "schema": "agent_config",
    "version": 2,
    "data": {
        "systemPrompt": "You are helpful",
        "tools": [
            {
                "type": "vectorSearch",
                "provider": "pinecone",
                "index": "my-index",
                "namespace": "docs",
                "topK": 10
            }
        ]
    }
}

# Create all tools
tools = await create_tools_from_agent_config(
    agent_config=agent_config,
    account_id=123,
    db=db_session,
    auth_token=jwt_token
)

# Use tools with LangChain agent
agent = create_openai_tools_agent(llm, tools, prompt_template)
```

### Creating a Single Tool

```python
from src.tools import create_tool_from_config

tool_config = {
    "type": "vectorSearch",
    "provider": "pinecone",
    "index": "docs",
    "namespace": "api-ref",
    "description": "API documentation search",
    "topK": 15
}

tool = await create_tool_from_config(
    tool_config=tool_config,
    account_id=123,
    db=db_session,
    auth_token=jwt_token
)
```

### Backwards Compatibility (v1 Configs)

The factory automatically handles v1 configs with `knowledgeBases`:

```python
# v1 config
agent_config = {
    "schema": "agent_config",
    "version": 1,
    "data": {
        "systemPrompt": "You are helpful",
        "knowledgeBases": [
            {
                "provider": "pinecone",
                "index": "my-index",
                "namespace": "docs"
            }
        ]
    }
}

# Still works! Automatically converts to vectorSearch tools
tools = await create_tools_from_agent_config(
    agent_config=agent_config,
    account_id=123,
    db=db_session,
    auth_token=jwt_token
)
```

## Available Tools

### 1. Vector Search

**Type:** `vectorSearch`

**Description:** Fast semantic search over vector databases (Pinecone). Returns results based on vector similarity alone.

**Use When:** Speed is important and you need quick results with good-enough relevance.

**Config:**
```json
{
  "type": "vectorSearch",
  "provider": "pinecone",
  "index": "index-name",
  "namespace": "namespace-name",
  "description": "What this knowledge base contains",
  "topK": 10
}
```

**Requirements:**
- Pinecone API key in user credentials
- `EMBEDDINGS_API_URL` environment variable
- Vector database index exists with embeddings

**Returns:**
```python
{
  "results": [
    {
      "metadata": {...},
      "score": 0.95,
      "id": "chunk-123"
    },
    ...
  ],
  "namespace": "docs",
  "index": "my-index"
}
```

---

### 2. Vector Search with Re-ranking

**Type:** `vectorSearchWithReranking`

**Description:** High-quality semantic search with two-stage retrieval. First retrieves more candidates (topK), then re-ranks them with a cross-encoder to return the most relevant subset (topN).

**Use When:** Quality is critical and you need the most relevant results, especially for complex queries.

**Config:**
```json
{
  "type": "vectorSearchWithReranking",
  "provider": "pinecone",
  "index": "index-name",
  "namespace": "namespace-name",
  "description": "What this knowledge base contains",
  "topK": 20,
  "topN": 5
}
```

**Requirements:**
- Pinecone API key in user credentials
- `EMBEDDINGS_API_URL` environment variable
- `RERANKER_API_URL` environment variable (falls back to similarity search if not set)
- Vector database index exists with embeddings

**How it works:**
1. **Stage 1**: Retrieve `topK` candidates using vector similarity (fast)
2. **Stage 2**: Re-rank candidates using cross-encoder model (accurate)
3. **Stage 3**: Return top `topN` results after re-ranking

**Returns:**
```python
{
  "results": [
    {
      "metadata": {...},
      "score": 0.95,          # Re-ranking score
      "similarity_score": 0.87,  # Original vector similarity
      "id": "chunk-123"
    },
    ...
  ],
  "namespace": "docs",
  "index": "my-index",
  "reranking_applied": true,
  "initial_candidates": 20,
  "final_results": 5
}
```

**Performance Notes:**
- Slower than `vectorSearch` due to re-ranking step
- More accurate results, especially for complex queries
- Gracefully falls back to similarity search if reranker unavailable

---

### Choosing Between Tools

| Feature | Vector Search | Vector Search with Re-ranking |
|---------|--------------|------------------------------|
| Speed | ⚡ Fast | 🐢 Slower (2-stage) |
| Accuracy | ✓ Good | ✓✓ Excellent |
| Best for | Quick lookups, FAQs | Complex queries, critical accuracy |
| API calls | 1 (embedding) | 2 (embedding + reranker) |
| Fallback | N/A | Falls back to similarity search |
| topK results | Direct results | Initial candidates for reranking |
| topN results | N/A (same as topK) | Final reranked results |

**Rule of thumb:**
- Use `vectorSearch` for speed-critical applications (chat, quick lookups)
- Use `vectorSearchWithReranking` for quality-critical applications (support, research)
- Agents can have both tools and let the LLM choose based on context!

## Adding New Tools

### Step 1: Create Tool Module

Create a new file like `src/tools/my_tool.py`:

```python
"""
My Custom Tool

Description of what this tool does.
"""
from typing import Dict, Any, Optional
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


async def create_my_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Any,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create my custom tool.
    
    Args:
        tool_config: Tool configuration with type-specific fields
        account_id: Account ID for fetching credentials
        db: Database session
        auth_token: Authentication token
        **kwargs: Additional context
        
    Returns:
        StructuredTool instance or None if setup fails
    """
    # Extract config
    my_param = tool_config.get('myParam')
    
    # Validate
    if not my_param:
        print("[MY TOOL] Missing required parameter: myParam")
        return None
    
    # Define tool implementation
    async def tool_impl(input_param: str) -> Dict:
        """The actual tool logic."""
        # Do something useful
        result = f"Processed: {input_param}"
        return {"result": result}
    
    # Define argument schema
    class MyToolArgs(BaseModel):
        input_param: str = Field(description="Input parameter description")
    
    # Create and return tool
    return StructuredTool(
        func=tool_impl,
        coroutine=tool_impl,
        name="my_tool",
        description="What my tool does",
        args_schema=MyToolArgs
    )
```

### Step 2: Register Tool

Add registration to `src/tools/auto_register.py`:

```python
from .my_tool import create_my_tool

def register_all_tools():
    register_tool_type("vectorSearch", create_vector_search_tool)
    register_tool_type("myTool", create_my_tool)  # Add this line
    # ...
```

### Step 3: Add Schema Definition

Update `src/schemas/agent_config.v2.json` to include your tool type in the `oneOf` array:

```json
{
  "$defs": {
    "tool": {
      "oneOf": [
        {"$ref": "#/$defs/vectorSearchTool"},
        {"$ref": "#/$defs/myTool"}
      ]
    },
    "myTool": {
      "type": "object",
      "required": ["type", "myParam"],
      "properties": {
        "type": {"const": "myTool"},
        "myParam": {"type": "string"}
      }
    }
  }
}
```

### Step 4: Test

```python
tool_config = {
    "type": "myTool",
    "myParam": "test value"
}

tool = await create_tool_from_config(tool_config, account_id, db)
```

## Tool Builder Signature

All tool builders must follow this signature:

```python
async def create_tool_name(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Any,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create a tool instance.
    
    Args:
        tool_config: Tool configuration dict from agent config
        account_id: Account ID for credential lookups
        db: Database session
        auth_token: JWT or API key for external API calls
        **kwargs: Additional context (request, etc.)
        
    Returns:
        StructuredTool instance or None if creation fails
    """
    pass
```

## Error Handling

The factory handles errors gracefully:

```python
# Unknown tool type
tool_config = {"type": "unknownTool"}
tool = await create_tool_from_config(tool_config, ...)
# Returns: None (with warning logged)

# Missing required fields
tool_config = {"type": "vectorSearch", "provider": "pinecone"}
tool = await create_tool_from_config(tool_config, ...)
# Returns: None (with error logged)

# Builder raises exception
tool = await create_tool_from_config(bad_config, ...)
# Returns: None (with traceback logged)
```

## Debugging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Factory logs:
# [TOOL FACTORY] Creating tools from agent config v2
# [TOOL FACTORY] Found 2 tools (v2 format)
# [TOOL FACTORY] Creating tool of type: vectorSearch
# [VECTOR SEARCH TOOL] Created tool for pinecone/docs/api-ref
# [TOOL FACTORY] Created 2 tools successfully
```

## Testing

```python
import pytest
from src.tools import create_tool_from_config, ToolRegistry

def test_tool_registry():
    """Test tool registry."""
    assert ToolRegistry.is_registered("vectorSearch")
    assert "vectorSearch" in ToolRegistry.list_types()

@pytest.mark.asyncio
async def test_create_vector_search_tool(db_session, account_id):
    """Test creating vector search tool."""
    tool_config = {
        "type": "vectorSearch",
        "provider": "pinecone",
        "index": "test-index",
        "namespace": "test-ns",
        "topK": 5
    }
    
    tool = await create_tool_from_config(
        tool_config=tool_config,
        account_id=account_id,
        db=db_session,
        auth_token="test-token"
    )
    
    assert tool is not None
    assert tool.name == "search_test-ns"
    assert "test-ns knowledge base" in tool.description

@pytest.mark.asyncio
async def test_v1_backwards_compatibility(db_session, account_id):
    """Test v1 config conversion."""
    agent_config = {
        "version": 1,
        "data": {
            "systemPrompt": "Test",
            "knowledgeBases": [
                {"provider": "pinecone", "index": "idx", "namespace": "ns"}
            ]
        }
    }
    
    tools = await create_tools_from_agent_config(
        agent_config=agent_config,
        account_id=account_id,
        db=db_session
    )
    
    assert len(tools) == 1
    assert tools[0].name == "search_ns"
```

## Performance Considerations

- **Tool Creation**: Tools are created once per agent session, not per request
- **Credentials**: Cached in tool closure, not fetched on every call
- **Connection Pooling**: Use aiohttp sessions for HTTP calls
- **Error Recovery**: Failed tool creation doesn't crash the agent

## Security

- **Credential Access**: Tools only access credentials for their account
- **API Keys**: Encrypted at rest, decrypted only when needed
- **Auth Tokens**: Passed through securely to external APIs
- **Namespace Isolation**: Vector search respects namespace boundaries

## Future Enhancements

Planned tool types:

- `webSearch` - Real-time web search (Brave, Serper)
- `calculator` - Mathematical calculations
- `apiCall` - Custom REST API integration
- `sqlQuery` - Database queries with safety constraints
- `codeExecution` - Sandboxed Python/JavaScript execution
- `email` - Send emails via configured providers
- `calendar` - Calendar operations
- `fileOperation` - Read/write files with permissions

## Related Documentation

- **Agent Config v2:** `src/schemas/AGENT_CONFIG_V2_GUIDE.md`
- **Schema Files:** `src/schemas/agent_config.v2.json`
- **Examples:** `src/schemas/examples/`
- **Completion Endpoint:** `src/routers/agents/completion.py`
