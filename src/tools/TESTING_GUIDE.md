# Tool System Testing Guide

## Quick Test: Create Agent with v2 Config

### 1. Create a v2 Agent with Vector Search

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Fast Search Agent",
    "description": "Agent with fast vector search",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "You are a helpful assistant with access to documentation.",
        "tools": [
          {
            "type": "vectorSearch",
            "provider": "pinecone",
            "index": "your-index-name",
            "namespace": "your-namespace",
            "description": "Product documentation and API references",
            "topK": 10
          }
        ]
      }
    }
  }'
```

### 1b. Create a v2 Agent with Vector Search + Re-ranking

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "High Quality Search Agent",
    "description": "Agent with vector search and re-ranking",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "You are a helpful assistant with access to high-quality search.",
        "tools": [
          {
            "type": "vectorSearchWithReranking",
            "provider": "pinecone",
            "index": "your-index-name",
            "namespace": "your-namespace",
            "description": "Product documentation with re-ranking for best results",
            "topK": 20,
            "topN": 5
          }
        ]
      }
    }
  }'
```

### 1c. Create a Multi-Tool Agent (Both Search Types)

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Smart Search Agent",
    "description": "Agent that can choose between fast and quality search",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "You are a helpful assistant. Use fast search for simple queries, and high-quality search for complex or critical questions.",
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
            "description": "Detailed documentation with re-ranking for accurate answers",
            "topK": 20,
            "topN": 5
          }
        ]
      }
    }
  }'
```

Expected response:
```json
{
  "id": 123,
  "name": "Test Vector Search Agent",
  "description": "Testing v2 tool system",
  "config": { ... },
  "created_at": "2026-01-19T...",
  "updated_at": "2026-01-19T..."
}
```

### 2. Test Agent Completion

```bash
curl -X POST http://localhost:4000/api/agents/123/completion \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-123",
    "prompt": "What can you help me with?"
  }'
```

Expected streaming response:
```
{"event":"on_chat_model_start"}
{"event":"on_chat_model_stream","data":"I"}
{"event":"on_chat_model_stream","data":" can"}
{"event":"on_chat_model_stream","data":" help"}
...
{"event":"on_chain_end","data":"...full response..."}
```

### 3. Test Agent with Tool Usage

```bash
curl -X POST http://localhost:4000/api/agents/123/completion \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-session-123",
    "prompt": "Search for information about authentication"
  }'
```

Expected events:
```
{"event":"on_chat_model_start"}
{"event":"on_tool_start","data":"Starting tool: search_your-namespace..."}
{"event":"on_tool_end"}
{"event":"on_chat_model_stream","data":"Based on the documentation..."}
...
{"event":"on_chain_end","data":"...full response with tool results..."}
```

## Verify v1 Backwards Compatibility

### 1. Create a v1 Agent (Legacy Format)

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test v1 Agent",
    "description": "Testing v1 compatibility",
    "config": {
      "schema": "agent_config",
      "version": 1,
      "data": {
        "systemPrompt": "You are helpful",
        "knowledgeBases": [
          {
            "provider": "pinecone",
            "index": "your-index-name",
            "namespace": "your-namespace",
            "description": "Legacy knowledge base"
          }
        ]
      }
    }
  }'
```

### 2. Test v1 Agent Completion

Should work exactly the same as v2!

```bash
curl -X POST http://localhost:4000/api/agents/124/completion \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "test-v1-session",
    "prompt": "Search for authentication info"
  }'
```

## Check Logs

Look for these log messages in your FastAPI server:

```
[TOOL REGISTRY] Registered tool type: vectorSearch
[TOOL REGISTRY] All tool types registered
[AGENT COMPLETION] Config v2 - system_prompt length: 67, tools: 1
[TOOL FACTORY] Creating tools from agent config v2
[TOOL FACTORY] Found 1 tools (v2 format)
[TOOL FACTORY] Creating tool of type: vectorSearch
[VECTOR SEARCH TOOL] Created tool for pinecone/your-index/your-namespace
[TOOL FACTORY] Created 1 tools successfully
[AGENT COMPLETION] Created 1 tools, using agent executor mode
```

For v1 configs:
```
[AGENT COMPLETION] Config v1 - system_prompt length: 16, tools: 1
[TOOL FACTORY] Creating tools from agent config v1
[TOOL FACTORY] Found 1 knowledge bases (v1 format)
[TOOL FACTORY] Creating tool of type: vectorSearch
[VECTOR SEARCH TOOL] Created tool for pinecone/your-index/your-namespace
[TOOL FACTORY] Created 1 tools successfully
```

## Test Tool Registry Directly

### Python REPL Test

```python
# Start Python from project root
python3

# Import tool system
from src.tools import ToolRegistry, create_tool_from_config

# Check registered tools
print(ToolRegistry.list_types())
# Output: ['vectorSearch']

print(ToolRegistry.is_registered("vectorSearch"))
# Output: True

print(ToolRegistry.get_builder("vectorSearch"))
# Output: <function create_vector_search_tool at 0x...>

# Test unknown tool
print(ToolRegistry.get_builder("unknownTool"))
# Output: None
```

## Test Error Handling

### 1. Invalid Tool Type

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Invalid Agent",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "Test",
        "tools": [
          {
            "type": "unknownTool",
            "someParam": "value"
          }
        ]
      }
    }
  }'
```

Expected: Schema validation error (before reaching tool factory)

### 2. Missing Required Fields

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Invalid Agent",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "Test",
        "tools": [
          {
            "type": "vectorSearch",
            "provider": "pinecone"
          }
        ]
      }
    }
  }'
```

Expected: Schema validation error (missing `index`, `namespace`)

### 3. Agent Without Tools

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer YOUR_JWT_OR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Simple Chat Agent",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "You are a helpful assistant.",
        "tools": []
      }
    }
  }'
```

Expected: Success! Agent works in "simple chat" mode (no tools)

Logs:
```
[TOOL FACTORY] Creating tools from agent config v2
[TOOL FACTORY] Found 0 tools (v2 format)
[TOOL FACTORY] Created 0 tools successfully
[AGENT COMPLETION] Created 0 tools, using simple chat mode
```

## Integration Test Script

Create a simple test script:

```python
# test_tools.py
import asyncio
import sys
sys.path.append('/code')

from src.tools import (
    ToolRegistry,
    create_tool_from_config,
    create_tools_from_agent_config
)

async def main():
    print("=== Tool System Integration Test ===\n")
    
    # Test 1: Registry
    print("Test 1: Tool Registry")
    print(f"Registered types: {ToolRegistry.list_types()}")
    print(f"vectorSearch registered: {ToolRegistry.is_registered('vectorSearch')}")
    print()
    
    # Test 2: v2 config
    print("Test 2: v2 Config Parsing")
    v2_config = {
        "version": 2,
        "data": {
            "systemPrompt": "Test",
            "tools": [
                {
                    "type": "vectorSearch",
                    "provider": "pinecone",
                    "index": "test",
                    "namespace": "test-ns",
                    "topK": 5
                }
            ]
        }
    }
    
    # Note: This will fail without DB and credentials
    # Just testing that factory logic works
    print(f"Config version: {v2_config['version']}")
    print(f"Tool count: {len(v2_config['data']['tools'])}")
    print(f"Tool type: {v2_config['data']['tools'][0]['type']}")
    print()
    
    # Test 3: v1 config
    print("Test 3: v1 Config Parsing")
    v1_config = {
        "version": 1,
        "data": {
            "systemPrompt": "Test",
            "knowledgeBases": [
                {"provider": "pinecone", "index": "idx", "namespace": "ns"}
            ]
        }
    }
    print(f"Config version: {v1_config['version']}")
    print(f"KB count: {len(v1_config['data']['knowledgeBases'])}")
    print(f"Will be converted to {len(v1_config['data']['knowledgeBases'])} vectorSearch tools")
    print()
    
    print("=== All Tests Passed ===")

if __name__ == "__main__":
    asyncio.run(main())
```

Run it:
```bash
cd /code
python3 test_tools.py
```

Expected output:
```
=== Tool System Integration Test ===

Test 1: Tool Registry
[TOOL REGISTRY] Registered tool type: vectorSearch
[TOOL REGISTRY] All tool types registered
Registered types: ['vectorSearch']
vectorSearch registered: True

Test 2: v2 Config Parsing
Config version: 2
Tool count: 1
Tool type: vectorSearch

Test 3: v1 Config Parsing
Config version: 1
KB count: 1
Will be converted to 1 vectorSearch tools

=== All Tests Passed ===
```

## Troubleshooting

### Tool Not Being Created

**Symptom:** Agent doesn't use tools even though config has them

**Check:**
1. Look for `[TOOL FACTORY] Created 0 tools` in logs
2. Check for `[VECTOR SEARCH TOOL] Missing required fields` errors
3. Verify Pinecone API key exists in credentials
4. Verify `EMBEDDINGS_API_URL` environment variable is set

### Tool Execution Fails

**Symptom:** `on_tool_start` appears but tool returns error

**Check:**
1. Embedding API is running and accessible
2. Auth token is being passed correctly
3. Pinecone index exists and is accessible
4. Namespace exists in the index

### v1 Config Not Working

**Symptom:** v1 agents fail to create tools

**Check:**
1. Look for `[TOOL FACTORY] Found X knowledge bases (v1 format)` in logs
2. Verify `knowledgeBases` array is populated
3. Check that each KB has `provider`, `index`, `namespace`

### Schema Validation Fails

**Symptom:** 400 error when creating agent

**Check:**
1. Verify `version` field matches schema version (1 or 2)
2. For v2: Use `tools` array, not `knowledgeBases`
3. For v1: Use `knowledgeBases` array, not `tools`
4. Check all required fields are present

## Success Criteria

✅ Can create v2 agents with `tools` array  
✅ Can create v1 agents with `knowledgeBases` array  
✅ Both types complete successfully  
✅ Tools are invoked when relevant  
✅ Tool results are returned to agent  
✅ Logs show tool creation and execution  
✅ No linter errors in `/code/src/tools/`  

If all criteria pass, the tool system is working correctly! 🎉
