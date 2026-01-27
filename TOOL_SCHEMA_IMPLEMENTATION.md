# Tool Schema Implementation Summary

## Overview

Implemented a comprehensive hybrid approach for strongly-typed tool outputs on the Kalygo platform. This allows frontend developers to build type-safe UIs around agent tool calls.

## What Was Changed

### 1. **Created New Schema Files**

#### `/code/src/schemas/chat_message.v2.json`
- Defines structured tool call format with `toolType`, `toolName`, `input`, `output`
- Includes comprehensive metadata schemas for both ingestion types:
  - **Text/Document Metadata** - from `.txt`/`.md` files
  - **Q&A Metadata** - from `.csv` files
- Uses `oneOf` for discriminated unions
- Provides complete examples

#### `/code/src/schemas/agent_streaming_events.v1.json`
- Documents all streaming events emitted by the agent loop
- Defines event types: `error`, `on_chain_start`, `on_chain_end`, `on_chat_model_start`, `on_chat_model_stream`, `on_tool_start`, `on_tool_end`
- Includes `toolCalls` in `on_chain_end` event
- Complete with examples

### 2. **Updated Agent Completion Handler**

#### `/code/src/routers/agents/completion.py`
- **Renamed** `retrieval_calls` → `tool_calls` throughout (consistent naming)
- **Updated JSON keys** in events from `retrieval_calls` → `toolCalls` (camelCase)
- **Restructured tool call format** to v2 schema:
  ```python
  {
      "toolType": "vectorSearch" | "vectorSearchWithReranking",
      "toolName": "search_docs",  # actual tool instance name
      "input": {
          "query": "...",
          "topK": 10
      },
      "output": {
          "results": [...],  # metadata kept as-is from ingestion
          "namespace": "...",
          "index": "..."
      }
  }
  ```
- **Removed content duplication** - no longer extracts/reformats content from metadata
- **Metadata preserved** - passes through exactly as stored in Pinecone
- **Updated validation** - uses `chat_message` schema v2

### 3. **Updated Tool Types**

#### `/code/src/tools/vector_search.py` (Previous Session)
- Added TypedDict types for output schemas
- Changed `db: Any` → `db: Session` for better typing
- Added return type annotations

### 4. **Created Documentation**

#### `/code/READMEs/agent_tool_schemas.md`
- Comprehensive guide for frontend developers
- TypeScript type examples
- UI component examples
- Migration guide from v1 to v2
- Event stream examples

## Schema Structure

### Tool Call Format

```typescript
interface ToolCall {
  toolType: "vectorSearch" | "vectorSearchWithReranking";
  toolName: string;
  input: {
    query: string;
    topK?: number;
  };
  output: {
    results: VectorSearchResult[];
    namespace: string;
    index: string;
  };
}
```

### Vector Search Result

```typescript
interface VectorSearchResult {
  id: string;
  score: number;
  metadata: TextDocumentMetadata | QAMetadata;
}
```

### Metadata Types

#### Text/Document Metadata
```typescript
interface TextDocumentMetadata {
  filename: string;
  chunkId: number;
  content: string;
  chunkSizeTokens: number;
  uploadTimestamp: string;
  chunkNumber: number;
  totalChunks: number;
  // Custom YAML front matter fields
  [key: `file_${string}`]: string;
}
```

#### Q&A Metadata
```typescript
interface QAMetadata {
  row_number: number;
  q: string;
  a: string;
  content: string;
  filename: string;
  user_id: string;
  user_email: string;
  upload_timestamp: string;
  created_at?: string;
  last_edited_at?: string;
}
```

## Benefits

### For Backend
✅ **Type safety** - Pydantic models provide validation  
✅ **Consistent structure** - All tools follow same pattern  
✅ **Extensible** - Easy to add new tool types  
✅ **Self-documenting** - Schemas serve as documentation  

### For Frontend
✅ **Type-safe UIs** - Generate TypeScript types from JSON schemas  
✅ **Discriminated unions** - `toolType` field enables clean conditionals  
✅ **Clear contracts** - Know exactly what to expect  
✅ **Rich metadata** - Access all ingestion metadata for UI rendering  

## Migration Path

### Before (v1)
```json
{
  "name": "retrieval with re-ranking",
  "query": "ollama",
  "results": [
    {
      "chunk_id": "abc",
      "score": 0.92,
      "content": "...",
      "metadata": {...}
    }
  ]
}
```

### After (v2)
```json
{
  "toolType": "vectorSearchWithReranking",
  "toolName": "search_rerank_docs",
  "input": {
    "query": "ollama",
    "topK": 10
  },
  "output": {
    "results": [
      {
        "id": "abc",
        "score": 0.92,
        "metadata": {...}
      }
    ],
    "namespace": "docs",
    "index": "kb"
  }
}
```

## Next Steps

### Immediate
- ✅ Schema v2 created
- ✅ Backend emits v2 format
- ✅ Documentation written

### Future (Optional)
- [ ] Create API endpoint to fetch tool metadata schemas per agent
- [ ] Add more tool types (web search, calculator, etc.)
- [ ] Generate TypeScript types from schemas
- [ ] Add output schema validation before emitting
- [ ] Support custom metadata schemas per namespace

## Testing

To verify the changes:

1. **Create an agent** with vector search tools
2. **Send a query** that triggers the tool
3. **Inspect the `on_chain_end` event** - should contain `toolCalls` array
4. **Verify structure** - should match `chat_message.v2.json` schema
5. **Check metadata** - should be preserved exactly as ingested

Example test query:
```bash
curl -X POST https://api.kalygo.io/agents/123/completion \
  -H "Authorization: Bearer $JWT" \
  -d '{"prompt": "What is Ollama?", "sessionId": "..."}'
```

Look for the `toolCalls` field in the response stream.

## Files Changed

1. ✅ `/code/src/schemas/chat_message.v2.json` (created)
2. ✅ `/code/src/schemas/agent_streaming_events.v1.json` (created)
3. ✅ `/code/src/routers/agents/completion.py` (updated)
4. ✅ `/code/src/tools/vector_search.py` (updated - previous session)
5. ✅ `/code/READMEs/agent_tool_schemas.md` (created)
6. ✅ `/code/TOOL_SCHEMA_IMPLEMENTATION.md` (this file)

## Schema Sources

The metadata schemas were derived from analyzing:
- `/code/src/routers/localAgent/upload_text.py` (local text ingestion)
- `https://github.com/Kalygo-io/kalygo3-txt-ingest-cloud-function-python/blob/main/helpers/text_processor.py` (cloud text worker)
- `https://github.com/Kalygo-io/kalygo3-qna-ingest-cloud-function-python/blob/main/helpers/csv_processor.py` (cloud Q&A worker)

This ensures the schemas match exactly what's stored in Pinecone.
