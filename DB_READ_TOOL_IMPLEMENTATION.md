# Database Read Tool Implementation Summary

## Overview

Successfully implemented a new tool type (`dbRead`) that allows agents to query structured data from Kalygo database tables. This enables agents to access and reason about user-specific data like chat sessions, usage credits, and ingestion logs.

## What Was Implemented

### 1. **Core Tool Implementation**

**File:** `/code/src/tools/db_read.py`

- Created `create_db_read_tool()` function following the same pattern as vector search
- Implements security features:
  - Table whitelist (only specific tables allowed)
  - Account scoping (users can only query their own data)
  - Sensitive column filtering (passwords, keys, etc. automatically excluded)
- Supports flexible querying:
  - Custom filters
  - Column selection
  - Pagination (limit/offset)
- Returns strongly-typed results with TypedDict definitions

**Whitelisted Tables:**
- `chat_app_sessions` - User's chat sessions
- `chat_app_messages` - Messages in sessions
- `usage_credits` - User's credit balance
- `vector_db_ingestion_log` - Document upload history
- `api_keys` - User's API keys

### 2. **Tool Registration**

**File:** `/code/src/tools/auto_register.py`

Added registration of the new tool type:
```python
register_tool_type("dbRead", create_db_read_tool)
```

### 3. **Schema Definitions**

#### Agent Configuration Schema
**File:** `/code/src/schemas/agent_config.v2.json`

Added `dbReadTool` definition:
```json
{
  "type": "dbRead",
  "table": "chat_app_sessions",
  "description": "Query chat sessions",
  "columns": ["id", "session_id", "title"],
  "limit": 50
}
```

#### Chat Message Schema  
**File:** `/code/src/schemas/chat_message.v2.json`

Added `dbReadToolCall` definition with full input/output structure:
```json
{
  "toolType": "dbRead",
  "toolName": "query_chat_app_sessions",
  "input": {
    "filters": {...},
    "limit": 10,
    "offset": 0
  },
  "output": {
    "results": [{...}],
    "table": "chat_app_sessions",
    "count": 1
  }
}
```

### 4. **Agent Completion Handler**

**File:** `/code/src/routers/agents/completion.py`

Updated tool call tracking to handle `query_*` tools:
- Detects tools starting with `query_` prefix
- Formats tool calls according to v2 schema
- Includes input parameters (filters, limit, offset)
- Includes output results (results array, table name, count)

### 5. **Documentation**

**File:** `/code/READMEs/db_read_tool.md`

Comprehensive documentation including:
- Configuration options
- Security features
- Allowed tables and their columns
- Complete examples
- Best practices
- Troubleshooting guide

## How It Works

### 1. **Configuration**

Add the tool to an agent's config:

```json
{
  "schema": "agent_config",
  "version": 2,
  "data": {
    "systemPrompt": "You are a helpful assistant...",
    "tools": [
      {
        "type": "dbRead",
        "table": "chat_app_sessions",
        "description": "Query user's chat sessions",
        "limit": 20
      }
    ]
  }
}
```

### 2. **Tool Creation**

When the agent is loaded:
1. Tool factory reads the config
2. Calls `create_db_read_tool()` with the config
3. Tool validates the table is whitelisted
4. Returns a `StructuredTool` named `query_{table_name}`

### 3. **Runtime Execution**

When the LLM decides to use the tool:
1. LangChain calls the tool with optional filters/limit/offset
2. Tool builds a SQLAlchemy query
3. Automatically applies `account_id` filter (security)
4. Executes query and formats results
5. Returns structured output

### 4. **Response Formatting**

The agent completion handler:
1. Detects `query_*` tool completion
2. Formats the tool call in v2 schema format
3. Includes it in the `toolCalls` array
4. Stores in database and streams to frontend

## Security Features

### ✅ Table Whitelist
Only explicitly allowed tables can be queried. System tables are protected.

### ✅ Account Scoping  
All queries automatically filter by `account_id`. Users can only see their own data.

```python
if is_account_scoped:
    query = query.filter(model_class.account_id == account_id)
```

### ✅ Sensitive Column Filtering
Automatically excludes:
- `hashed_password`
- `reset_token`
- `encrypted_api_key`
- `key_hash`

### ✅ Pagination Limits
Maximum 100 rows per query to prevent performance issues.

## Example Usage

### Support Agent with Session History

```json
{
  "name": "Support Assistant",
  "config": {
    "schema": "agent_config",
    "version": 2,
    "data": {
      "systemPrompt": "You help users with their chat history and usage.",
      "tools": [
        {
          "type": "dbRead",
          "table": "chat_app_sessions",
          "description": "Access user's chat sessions",
          "limit": 50
        },
        {
          "type": "dbRead",
          "table": "usage_credits",
          "description": "Check user's credits"
        }
      ]
    }
  }
}
```

**User Query:** "Show me my recent chat sessions"

**Tool Call:**
```json
{
  "toolType": "dbRead",
  "toolName": "query_chat_app_sessions",
  "input": {
    "filters": null,
    "limit": 10,
    "offset": 0
  },
  "output": {
    "results": [
      {
        "data": {
          "id": 1,
          "session_id": "f7e18bb1-fb1b-4739-8022-f6a21b83de23",
          "title": "AI School Chat",
          "created_at": "2026-01-26T20:00:00Z"
        }
      }
    ],
    "table": "chat_app_sessions",
    "count": 1
  }
}
```

## Adding New Tables

To allow agents to query a new table:

### 1. **Import the model**
```python
# In /code/src/tools/db_read.py
from src.db.models import YourNewModel
```

### 2. **Add to whitelist**
```python
ALLOWED_TABLES = {
    # ... existing tables
    "your_table_name": YourNewModel,
}

# If user-scoped:
ACCOUNT_SCOPED_TABLES = {
    # ... existing tables
    "your_table_name",
}
```

### 3. **Update schema**
```json
// In /code/src/schemas/agent_config.v2.json
"table": {
  "enum": [
    "chat_app_sessions",
    "your_table_name"
  ]
}
```

## Tool Call Flow

```
1. Agent Config
   └─> Tool Factory
       └─> create_db_read_tool()
           └─> StructuredTool created

2. LLM Decision
   └─> Calls query_{table} tool
       └─> Tool executes SQL query
           └─> Returns results

3. Agent Completion Handler
   └─> Detects query_* tool
       └─> Formats as dbReadToolCall
           └─> Adds to toolCalls array
               └─> Stores in DB
                   └─> Streams to frontend
```

## Files Modified/Created

### Created:
- ✅ `/code/src/tools/db_read.py` - Tool implementation
- ✅ `/code/READMEs/db_read_tool.md` - Documentation
- ✅ `/code/DB_READ_TOOL_IMPLEMENTATION.md` - This file

### Modified:
- ✅ `/code/src/tools/auto_register.py` - Registered dbRead tool
- ✅ `/code/src/schemas/agent_config.v2.json` - Added dbReadTool schema
- ✅ `/code/src/schemas/chat_message.v2.json` - Added dbReadToolCall schema  
- ✅ `/code/src/routers/agents/completion.py` - Handle query_* tools

## Testing

### 1. Create Test Agent

```bash
curl -X POST https://api.kalygo.io/api/agents \
  -H "Content-Type: application/json" \
  -H "Cookie: jwt=YOUR_JWT" \
  -d '{
    "name": "Session Manager",
    "config": {
      "schema": "agent_config",
      "version": 2,
      "data": {
        "systemPrompt": "You help manage chat sessions.",
        "tools": [{
          "type": "dbRead",
          "table": "chat_app_sessions",
          "description": "Query chat sessions",
          "limit": 10
        }]
      }
    }
  }'
```

### 2. Test Query

```bash
curl -X POST https://api.kalygo.io/api/agents/{agent_id}/completion \
  -H "Cookie: jwt=YOUR_JWT" \
  -d '{
    "sessionId": "...",
    "prompt": "Show me my recent chat sessions"
  }'
```

### 3. Expected Output

Look for in the stream:
- `toolCalls` array
- `toolType: "dbRead"`
- Results from database
- Only user's own data (account-scoped)

## Multiple DB Tools Example

You can give an agent access to multiple tables:

```json
{
  "tools": [
    {
      "type": "dbRead",
      "table": "chat_app_sessions",
      "description": "Query user's chat history"
    },
    {
      "type": "dbRead",
      "table": "usage_credits",
      "description": "Check credit balance"
    },
    {
      "type": "dbRead",
      "table": "vector_db_ingestion_log",
      "description": "View document upload history"
    },
    {
      "type": "vectorSearch",
      "provider": "pinecone",
      "index": "knowledge-base",
      "namespace": "docs",
      "description": "Search uploaded documents"
    }
  ]
}
```

This creates 4 tools for the agent:
- `query_chat_app_sessions`
- `query_usage_credits`
- `query_vector_db_ingestion_log`
- `search_docs`

## Comparison with Vector Search Tool

| Feature | Vector Search | DB Read |
|---------|--------------|---------|
| **Data Type** | Unstructured (text, embeddings) | Structured (rows, columns) |
| **Query Method** | Semantic similarity | SQL filters |
| **Tool Name** | `search_{namespace}` | `query_{table}` |
| **Config Key** | `namespace`, `index` | `table` |
| **Returns** | Ranked results with scores | Filtered rows |
| **Use Case** | "Find documents about X" | "Show my chat history" |

## Benefits

### For Backend:
✅ **Reuses existing pattern** - Follows vector search tool architecture  
✅ **Type-safe** - TypedDict output definitions  
✅ **Secure by default** - Whitelist + account scoping  
✅ **Extensible** - Easy to add new tables  

### For Agents:
✅ **Access to structured data** - Can reason about user's data  
✅ **Flexible queries** - Filters, pagination, column selection  
✅ **Automatic security** - Account scoping is transparent  

### For Frontend:
✅ **Typed output** - JSON schema defines structure  
✅ **Generate TypeScript types** - From JSON schemas  
✅ **Build custom UIs** - Different views for different tables  

## Next Steps (Optional)

- [ ] Add support for JOIN operations across tables
- [ ] Add aggregation functions (COUNT, SUM, AVG)
- [ ] Add ORDER BY support
- [ ] Create pre-built agent templates using DB tools
- [ ] Add more tables to whitelist as needed
- [ ] Create dashboard showing DB tool usage analytics

## Related Documentation

- [Tool Registry Architecture](/code/src/tools/ARCHITECTURE.md)
- [Agent Tool Schemas](/code/READMEs/agent_tool_schemas.md)
- [Database Read Tool Guide](/code/READMEs/db_read_tool.md)
