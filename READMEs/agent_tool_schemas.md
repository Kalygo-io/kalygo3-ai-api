# Agent Tool Output Schemas

This document describes the structured output schemas for tools used by agents on the Kalygo platform.

## Overview

All tool outputs follow a consistent, strongly-typed schema defined in JSON Schema format. This allows frontend developers to:

- **Build type-safe UIs** - TypeScript types can be auto-generated from JSON schemas
- **Know what to expect** - Clear documentation of all possible outputs
- **Handle different tool types** - Discriminated unions make it easy to render different UIs
- **Access metadata** - Rich metadata about each search result

## Schema Files

### Core Schemas

- **[`chat_message.v2.json`](/code/src/schemas/chat_message.v2.json)** - Defines the structure of chat messages including tool calls
- **[`agent_streaming_events.v1.json`](/code/src/schemas/agent_streaming_events.v1.json)** - Defines the streaming events emitted during agent execution
- **[`agent_config.v2.json`](/code/src/schemas/agent_config.v2.json)** - Defines the agent configuration format

## Tool Call Structure

All tool calls follow this consistent structure:

```typescript
interface ToolCall {
  toolType: string;      // Discriminator field (e.g., "vectorSearch", "vectorSearchWithReranking")
  toolName: string;      // Instance name (e.g., "search_docs", "search_rerank_kb")
  input: object;         // Tool-specific input parameters
  output: object;        // Tool-specific output data
}
```

### Example Tool Call

```json
{
  "toolType": "vectorSearch",
  "toolName": "search_docs",
  "input": {
    "query": "What is Ollama?",
    "topK": 5
  },
  "output": {
    "results": [
      {
        "id": "abc123...",
        "score": 0.92,
        "metadata": {
          "filename": "ollama_guide.md",
          "chunkId": 1,
          "content": "Ollama is an open-source tool...",
          "chunkSizeTokens": 150,
          "uploadTimestamp": "1706234567890",
          "chunkNumber": 1,
          "totalChunks": 5,
          "file_video_title": "What is Ollama?",
          "file_video_url": "https://youtube.com/watch?v=..."
        }
      }
    ],
    "namespace": "docs",
    "index": "knowledge-base"
  }
}
```

## Vector Search Result Metadata

Results from vector search contain metadata that varies based on how the data was ingested.

### Text/Document Metadata

Used for `.txt` and `.md` files ingested via `kalygo3-txt-ingest-cloud-function-python`.

```typescript
interface TextDocumentMetadata {
  // Required fields
  filename: string;           // Original filename
  chunkId: number;            // Chunk identifier (1-based)
  content: string;            // The actual text content
  chunkSizeTokens: number;    // Approximate token count
  uploadTimestamp: string;    // Unix timestamp in milliseconds
  chunkNumber: number;        // Chunk number for display (1-based)
  totalChunks: number;        // Total chunks in document
  
  // Optional YAML front matter fields (prefixed with "file_")
  file_video_title?: string;
  file_video_url?: string;
  file_tags?: string;
  // ... any other YAML fields
}
```

**Example:**

```json
{
  "filename": "ollama_guide.md",
  "chunkId": 1,
  "content": "Ollama is an open-source tool that allows you to run...",
  "chunkSizeTokens": 150,
  "uploadTimestamp": "1706234567890",
  "chunkNumber": 1,
  "totalChunks": 5,
  "file_video_title": "What is Ollama?",
  "file_video_url": "https://youtube.com/watch?v=abc123"
}
```

### Q&A Metadata

Used for `.csv` files with Q&A pairs ingested via `kalygo3-qna-ingest-cloud-function-python`.

```typescript
interface QAMetadata {
  // Required fields
  row_number: number;         // Row number in CSV (1-based)
  q: string;                  // The question
  a: string;                  // The answer
  content: string;            // Formatted as "Q: {q}\nA: {a}"
  filename: string;           // Original CSV filename
  user_id: string;            // User who uploaded
  user_email: string;         // User's email
  upload_timestamp: string;   // Unix timestamp in milliseconds
  
  // Optional fields
  created_at?: string;        // From CSV
  last_edited_at?: string;    // From CSV
}
```

**Example:**

```json
{
  "row_number": 15,
  "q": "What is the pricing for the Pro plan?",
  "a": "The Pro plan costs $29/month with unlimited projects",
  "content": "Q: What is the pricing for the Pro plan?\nA: The Pro plan costs $29/month with unlimited projects",
  "filename": "faq.csv",
  "user_id": "123",
  "user_email": "admin@kalygo.io",
  "upload_timestamp": "1706234567890",
  "created_at": "2024-01-15T10:00:00Z",
  "last_edited_at": "2024-01-20T15:30:00Z"
}
```

## Detecting Metadata Type

Use TypeScript type guards to detect which metadata type you're working with:

```typescript
function isQAMetadata(metadata: any): metadata is QAMetadata {
  return 'q' in metadata && 'a' in metadata;
}

function isTextDocumentMetadata(metadata: any): metadata is TextDocumentMetadata {
  return 'chunkId' in metadata && 'chunkNumber' in metadata;
}

// Usage
if (isQAMetadata(result.metadata)) {
  // Render Q&A card
  return <QACard question={result.metadata.q} answer={result.metadata.a} />;
} else if (isTextDocumentMetadata(result.metadata)) {
  // Render document chunk card
  return <DocumentCard content={result.metadata.content} />;
}
```

## Streaming Events

The agent endpoint streams events as JSON objects. See [`agent_streaming_events.v1.json`](/code/src/schemas/agent_streaming_events.v1.json) for the complete schema.

### Event Types

| Event | Description | Data Fields |
|-------|-------------|-------------|
| `error` | Error occurred | `data.error`, `data.message` |
| `on_chain_start` | Agent execution begins | None |
| `on_chain_end` | Agent execution completes | `data` (final response), `toolCalls` |
| `on_chat_model_start` | LLM starts processing | `toolCalls` (accumulated so far) |
| `on_chat_model_stream` | Token streamed from LLM | `data` (token) |
| `on_tool_start` | Tool execution begins | `data` (description) |
| `on_tool_end` | Tool execution completes | None |

### Example Event Stream

```javascript
// 1. Agent starts
{"event": "on_chain_start"}

// 2. LLM starts (no tools yet)
{"event": "on_chat_model_start", "toolCalls": []}

// 3. LLM streams response
{"event": "on_chat_model_stream", "data": "Let "}
{"event": "on_chat_model_stream", "data": "me "}
{"event": "on_chat_model_stream", "data": "search "}

// 4. Tool executes
{"event": "on_tool_start", "data": "Starting tool: search_docs with inputs: {'query': 'ollama'}"}
{"event": "on_tool_end"}

// 5. Agent completes with full response and tool calls
{
  "event": "on_chain_end",
  "data": "Ollama is an open-source tool...",
  "toolCalls": [
    {
      "toolType": "vectorSearch",
      "toolName": "search_docs",
      "input": {"query": "ollama", "topK": 5},
      "output": {
        "results": [...],
        "namespace": "docs",
        "index": "knowledge-base"
      }
    }
  ]
}
```

## Generating TypeScript Types

You can auto-generate TypeScript types from the JSON schemas using [`json-schema-to-typescript`](https://www.npmjs.com/package/json-schema-to-typescript):

```bash
# Install the tool
npm install -g json-schema-to-typescript

# Generate TypeScript types
json2ts src/schemas/chat_message.v2.json > frontend/types/ChatMessage.ts
json2ts src/schemas/agent_streaming_events.v1.json > frontend/types/AgentEvents.ts
```

## Migration from v1 to v2

If you're migrating from the old format, here's what changed:

### Old Format (v1)

```json
{
  "name": "retrieval with re-ranking",
  "query": "ollama",
  "results": [
    {
      "chunk_id": "abc123",
      "score": 0.92,
      "content": "...",
      "metadata": {...}
    }
  ],
  "namespace": "docs",
  "index": "knowledge-base"
}
```

### New Format (v2)

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
        "id": "abc123",
        "score": 0.92,
        "metadata": {...}
      }
    ],
    "namespace": "docs",
    "index": "knowledge-base"
  }
}
```

### Key Changes

1. ✅ **`toolType` field** - Identifies tool type for discriminated unions
2. ✅ **`toolName` field** - The actual instance name
3. ✅ **`input` object** - Separated input parameters
4. ✅ **`output` object** - Structured output data
5. ✅ **`results[].id`** - Renamed from `chunk_id`
6. ❌ **Removed `content` duplication** - Content is in `metadata.content`

## Frontend UI Components

### Example: Tool Call Renderer

```typescript
import { ToolCall } from './types/ChatMessage';

interface ToolCallProps {
  toolCall: ToolCall;
}

export function ToolCallRenderer({ toolCall }: ToolCallProps) {
  switch (toolCall.toolType) {
    case 'vectorSearch':
    case 'vectorSearchWithReranking':
      return <VectorSearchResults toolCall={toolCall} />;
    
    default:
      return <UnknownToolCall toolCall={toolCall} />;
  }
}

function VectorSearchResults({ toolCall }) {
  return (
    <div className="tool-results">
      <h4>🔍 Search: "{toolCall.input.query}"</h4>
      <div className="results">
        {toolCall.output.results.map((result) => (
          <ResultCard key={result.id} result={result} />
        ))}
      </div>
      <small>
        Source: {toolCall.output.namespace} ({toolCall.output.index})
      </small>
    </div>
  );
}

function ResultCard({ result }) {
  if (isQAMetadata(result.metadata)) {
    return (
      <div className="qa-card">
        <div className="question">Q: {result.metadata.q}</div>
        <div className="answer">A: {result.metadata.a}</div>
        <div className="score">Score: {result.score.toFixed(3)}</div>
      </div>
    );
  } else {
    return (
      <div className="doc-card">
        <div className="content">{result.metadata.content}</div>
        <div className="meta">
          {result.metadata.filename} • 
          Chunk {result.metadata.chunkNumber}/{result.metadata.totalChunks} •
          Score: {result.score.toFixed(3)}
        </div>
      </div>
    );
  }
}
```

## Support

For questions or issues with the tool schemas:

1. Check the [JSON Schema files](/code/src/schemas/) for the source of truth
2. Review the [examples](/code/src/schemas/chat_message.v2.json) in the schema files
3. Check the [ingestion worker code](https://github.com/Kalygo-io/) to see how metadata is created

## Related Documentation

- [Agent Configuration Schema](/code/src/schemas/agent_config.v2.json)
- [Tool Registry Architecture](/code/src/tools/ARCHITECTURE.md)
- [Tools Quick Reference](/code/src/tools/QUICK_REFERENCE.md)
