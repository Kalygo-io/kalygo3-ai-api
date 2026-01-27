# Database Read Tool

The Database Read Tool allows agents to query structured data from Kalygo database tables. This enables agents to access and reason about user-specific data like chat sessions, usage credits, and ingestion logs.

## Overview

- **Tool Type:** `dbTableRead`
- **Tool Name Pattern:** `query_{table_name}`
- **Security:** Account-scoped (agents can only access their own data)
- **Registration:** Automatically registered in the tool registry

## Configuration

Add the `dbTableRead` tool to your agent configuration:

```json
{
  "schema": "agent_config",
  "version": 2,
  "data": {
    "systemPrompt": "You are a helpful assistant...",
    "tools": [
      {
        "type": "dbTableRead",
        "table": "chat_app_sessions",
        "description": "Query user's chat sessions to provide history and context",
        "columns": ["id", "session_id", "title", "created_at"],
        "limit": 20
      },
      {
        "type": "dbTableRead",
        "table": "usage_credits",
        "description": "Check user's remaining usage credits",
        "limit": 1
      }
    ]
  }
}
```

## Configuration Options

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | ✅ | Must be `"dbTableRead"` |
| `table` | string | ✅ | Table name (see allowed tables below) |
| `description` | string | ❌ | Helps the LLM decide when to use this tool |
| `columns` | array | ❌ | Specific columns to return (defaults to all non-sensitive) |
| `limit` | number | ❌ | Default max rows to return (1-100, default: 50) |

## Allowed Tables

The following tables can be queried (all are account-scoped for security):

### 1. `chat_app_sessions`
Chat sessions created by the user.

**Columns:**
- `id` (integer) - Internal session ID
- `session_id` (UUID) - Public session identifier
- `chat_app_id` (string) - Agent/app identifier
- `account_id` (integer) - Owner account ID
- `created_at` (timestamp) - When session was created
- `title` (string) - Session title

**Example use case:** "Show me my recent chat sessions"

### 2. `chat_app_messages`  
Messages within chat sessions.

**Columns:**
- `id` (integer) - Message ID
- `chat_app_session_id` (integer) - Parent session ID
- `message` (JSON) - Message content with role and content
- `created_at` (timestamp) - When message was sent

**Example use case:** "Find my question about pricing from yesterday"

### 3. `usage_credits`
User's usage credit balance.

**Columns:**
- `id` (integer) - Credit record ID
- `account_id` (integer) - Owner account ID
- `amount` (float) - Credit balance
- `created_at` (timestamp) - Record creation time
- `updated_at` (timestamp) - Last update time

**Example use case:** "How many credits do I have left?"

### 4. `vector_db_ingestion_log`
History of vector database uploads/ingestions.

**Columns:**
- `id` (UUID) - Log entry ID
- `account_id` (integer) - Owner account ID
- `provider` (string) - Vector DB provider (e.g., "pinecone")
- `index_name` (string) - Index name
- `namespace` (string) - Namespace
- `filenames` (array) - Files that were ingested
- `operation_type` (enum) - INGEST, DELETE, UPDATE
- `status` (enum) - SUCCESS, FAILED, PARTIAL, PENDING
- `vectors_added` (integer) - Vectors successfully added
- `vectors_deleted` (integer) - Vectors deleted
- `vectors_failed` (integer) - Failed vectors
- `created_at` (timestamp) - When operation started
- `completed_at` (timestamp) - When operation finished
- `batch_number` (UUID) - Batch identifier
- `comment` (string) - Optional notes

**Example use case:** "Show me my recent document uploads"

### 5. `api_keys`
User's API keys for programmatic access.

**Columns:**
- `id` (integer) - Key ID
- `account_id` (integer) - Owner account ID
- `key_prefix` (string) - First 20 chars (for display)
- `name` (string) - User-friendly name
- `status` (enum) - active, revoked
- `created_at` (timestamp) - When key was created
- `last_used_at` (timestamp) - Last usage time

**Note:** `key_hash` is automatically excluded for security

**Example use case:** "List my active API keys"

## Security Features

### 1. Table Whitelist
Only tables explicitly listed in `ALLOWED_TABLES` can be queried. This prevents access to sensitive system tables.

### 2. Account Scoping
All queries are automatically filtered by `account_id`. Users can only see their own data.

```python
# Automatically applied:
query = query.filter(model_class.account_id == account_id)
```

### 3. Sensitive Column Filtering
The following columns are automatically excluded from results:
- `hashed_password`
- `reset_token`
- `encrypted_api_key`
- `key_hash`

## Tool Input Parameters

When the agent calls the tool, it can provide:

```typescript
interface QueryInput {
  filters?: Record<string, any>;  // Optional column filters
  limit?: number;                 // Max rows (1-100)
  offset?: number;                // Pagination offset
}
```

**Example:**
```json
{
  "filters": {
    "status": "active",
    "created_at": "2026-01-26"
  },
  "limit": 10,
  "offset": 0
}
```

## Tool Output Format

The tool returns results in this structure:

```typescript
interface DbReadOutput {
  results: Array<{
    data: Record<string, any>  // Row data as key-value pairs
  }>;
  table: string;               // Table that was queried
  count: number;               // Number of results returned
}
```

**Example:**
```json
{
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
```

## Complete Tool Call Example

Here's what a complete tool call looks like in the chat message:

```json
{
  "role": "ai",
  "content": "Here are your recent chat sessions...",
  "toolCalls": [
    {
      "toolType": "dbTableRead",
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
              "chat_app_id": "ai_school",
              "title": "AI School Chat",
              "created_at": "2026-01-26T20:00:00Z"
            }
          }
        ],
        "table": "chat_app_sessions",
        "count": 1
      }
    }
  ]
}
```

## Example Agent Configurations

### Support Agent with Session History

```json
{
  "schema": "agent_config",
  "version": 2,
  "data": {
    "systemPrompt": "You are a support assistant that helps users with their chat history and usage.",
    "tools": [
      {
        "type": "dbTableRead",
        "table": "chat_app_sessions",
        "description": "Access user's chat sessions to provide context and history",
        "limit": 50
      },
      {
        "type": "dbTableRead",
        "table": "usage_credits",
        "description": "Check user's remaining credits to answer billing questions"
      }
    ]
  }
}
```

### Data Management Agent

```json
{
  "schema": "agent_config",
  "version": 2,
  "data": {
    "systemPrompt": "You help users manage their uploaded documents and data.",
    "tools": [
      {
        "type": "dbTableRead",
        "table": "vector_db_ingestion_log",
        "description": "Query user's document upload history and status",
        "columns": ["id", "filenames", "status", "created_at", "namespace"],
        "limit": 25
      },
      {
        "type": "vectorSearch",
        "provider": "pinecone",
        "index": "knowledge-base",
        "namespace": "docs",
        "description": "Search through uploaded documents"
      }
    ]
  }
}
```

## Implementation Details

### File Structure

```
/code/src/tools/
  ├── db_read.py              # Tool implementation
  ├── auto_register.py        # Registers dbTableRead tool
  └── registry.py             # Tool registry

/code/src/schemas/
  ├── agent_config.v2.json    # Includes dbTableReadTool definition
  └── chat_message.v2.json    # Includes dbTableReadToolCall definition
```

### Adding New Tables

To whitelist a new table for agent access:

1. **Import the model** in `/code/src/tools/db_read.py`:
   ```python
   from src.db.models import YourNewModel
   ```

2. **Add to `ALLOWED_TABLES`**:
   ```python
   ALLOWED_TABLES = {
       # ... existing tables
       "your_table_name": YourNewModel,
   }
   ```

3. **If account-scoped**, add to `ACCOUNT_SCOPED_TABLES`:
   ```python
   ACCOUNT_SCOPED_TABLES = {
       # ... existing tables
       "your_table_name",
   }
   ```

4. **Update schema** in `/code/src/schemas/agent_config.v2.json`:
   ```json
   "enum": [
     "chat_app_sessions",
     "your_table_name"
   ]
   ```

## Testing

### 1. Create an agent with dbTableRead tool:

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
          "type": "dbTableRead",
          "table": "chat_app_sessions",
          "description": "Query chat sessions",
          "limit": 10
        }]
      }
    }
  }'
```

### 2. Test the tool:

```bash
curl -X POST https://api.kalygo.io/api/agents/{agent_id}/completion \
  -H "Cookie: jwt=YOUR_JWT" \
  -d '{
    "sessionId": "...",
    "prompt": "Show me my recent chat sessions"
  }'
```

### 3. Verify the output contains:

- `toolCalls` array with `toolType: "dbTableRead"`
- Results from the `chat_app_sessions` table
- Only the user's own sessions (account-scoped)

## Best Practices

### 1. **Specific Descriptions**
Help the LLM understand when to use the tool:

```json
{
  "type": "dbTableRead",
  "table": "usage_credits",
  "description": "Check user's remaining credit balance for billing questions"
}
```

### 2. **Limit Columns**
Only request needed columns for better performance:

```json
{
  "type": "dbTableRead",
  "table": "vector_db_ingestion_log",
  "columns": ["filenames", "status", "created_at"]
}
```

### 3. **Set Appropriate Limits**
Balance between completeness and performance:

```json
{
  "type": "dbTableRead",
  "table": "chat_app_sessions",
  "limit": 20  // Reasonable default
}
```

### 4. **Multiple Tools for Different Tables**
Give agents access to multiple tables:

```json
{
  "tools": [
    {
      "type": "dbTableRead",
      "table": "chat_app_sessions",
      "description": "User's chat history"
    },
    {
      "type": "dbTableRead",
      "table": "usage_credits",
      "description": "User's billing information"
    }
  ]
}
```

## Troubleshooting

### Tool not found

**Error:** "Unknown tool type 'dbTableRead'"

**Solution:** Tool registration happens on import. Restart the FastAPI server.

### Table not allowed

**Error:** "Table 'xyz' is not in allowed list"

**Solution:** Add the table to `ALLOWED_TABLES` in `/code/src/tools/db_read.py`

### No results returned

**Possible causes:**
1. User has no data in that table
2. Filters are too restrictive
3. Account scoping is working (user can only see their data)

**Debug:** Check server logs for query details.

## Related Documentation

- [Tool Registry Architecture](/code/src/tools/ARCHITECTURE.md)
- [Tool Schemas Documentation](/code/READMEs/agent_tool_schemas.md)
- [Agent Configuration Schema](/code/src/schemas/agent_config.v2.json)
