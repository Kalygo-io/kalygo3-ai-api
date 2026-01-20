# Tool Quick Reference Card

## Two Tool Types

### 🚀 Vector Search (Fast)

```json
{
  "type": "vectorSearch",
  "provider": "pinecone",
  "index": "your-index",
  "namespace": "your-namespace",
  "description": "What this contains",
  "topK": 10
}
```

**Speed**: ⚡ Fast (~100-200ms)  
**Accuracy**: ✓ Good  
**API Calls**: 1 (embedding only)  
**Tool Name**: `search_{namespace}`  
**Best For**: Quick lookups, FAQs, speed-critical

---

### 🎯 Vector Search with Re-ranking (Quality)

```json
{
  "type": "vectorSearchWithReranking",
  "provider": "pinecone",
  "index": "your-index",
  "namespace": "your-namespace",
  "description": "What this contains",
  "topK": 20,
  "topN": 5
}
```

**Speed**: 🐢 Slower (~300-500ms)  
**Accuracy**: ✓✓ Excellent  
**API Calls**: 2 (embedding + reranker)  
**Tool Name**: `search_rerank_{namespace}`  
**Best For**: Complex queries, quality-critical, research

---

## Agent Examples

### Simple Chat (No Tools)
```json
{
  "version": 2,
  "data": {
    "systemPrompt": "You are helpful",
    "tools": []
  }
}
```

### Fast Search Agent
```json
{
  "version": 2,
  "data": {
    "systemPrompt": "Fast assistant",
    "tools": [
      {"type": "vectorSearch", "provider": "pinecone", "index": "docs", "namespace": "api", "topK": 10}
    ]
  }
}
```

### Quality Search Agent
```json
{
  "version": 2,
  "data": {
    "systemPrompt": "Quality assistant",
    "tools": [
      {"type": "vectorSearchWithReranking", "provider": "pinecone", "index": "docs", "namespace": "support", "topK": 20, "topN": 5}
    ]
  }
}
```

### Smart Agent (Both Tools)
```json
{
  "version": 2,
  "data": {
    "systemPrompt": "Use fast search for simple queries, quality search for complex ones",
    "tools": [
      {"type": "vectorSearch", "provider": "pinecone", "index": "docs", "namespace": "quick", "topK": 10},
      {"type": "vectorSearchWithReranking", "provider": "pinecone", "index": "docs", "namespace": "detailed", "topK": 20, "topN": 5}
    ]
  }
}
```

---

## When to Use What

| Use Case | Tool |
|----------|------|
| FAQ lookup | `vectorSearch` |
| Quick reference | `vectorSearch` |
| Real-time chat | `vectorSearch` |
| High throughput | `vectorSearch` |
| Legal documents | `vectorSearchWithReranking` |
| Medical docs | `vectorSearchWithReranking` |
| Tech support | `vectorSearchWithReranking` |
| Research | `vectorSearchWithReranking` |
| Ambiguous queries | `vectorSearchWithReranking` |

---

## Environment Variables

### Required
- `EMBEDDINGS_API_URL` - For both tools

### Optional
- `RERANKER_API_URL` - For re-ranking (falls back gracefully if missing)

---

## Tool Registry

```python
from src.tools import ToolRegistry

# List available tools
print(ToolRegistry.list_types())
# ['vectorSearch', 'vectorSearchWithReranking']

# Check if registered
print(ToolRegistry.is_registered('vectorSearch'))
# True
```

---

## Create Tools

```python
from src.tools import create_tools_from_agent_config

tools = await create_tools_from_agent_config(
    agent_config=agent.config,
    account_id=account_id,
    db=db,
    auth_token=auth_token
)
```

---

## Logs to Look For

```
[TOOL REGISTRY] Registered tool type: vectorSearch
[TOOL REGISTRY] Registered tool type: vectorSearchWithReranking
[TOOL FACTORY] Creating tools from agent config v2
[TOOL FACTORY] Found 2 tools (v2 format)
[VECTOR SEARCH TOOL] Created tool for pinecone/docs/api
[VECTOR SEARCH WITH RERANKING] Created tool for pinecone/docs/support
[TOOL FACTORY] Created 2 tools successfully
```

---

## Common Issues

### Tool Not Created
**Check**: Pinecone API key in credentials  
**Check**: `EMBEDDINGS_API_URL` is set  
**Logs**: `[VECTOR SEARCH TOOL] No Pinecone API key found`

### Re-ranking Falls Back
**Check**: `RERANKER_API_URL` is set  
**Logs**: `[VECTOR SEARCH WITH RERANKING] Warning: RERANKER_API_URL not set, falling back to similarity search only`  
**Note**: This is graceful fallback, agent still works!

### Tool Not Used
**Check**: Tool description matches query context  
**Check**: LLM can see the tool in system prompt  
**Logs**: Look for `on_tool_start` events

---

## Testing Commands

### Create Fast Agent
```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer TOKEN" \
  -d '{"name":"Fast","config":{"version":2,"data":{"systemPrompt":"Fast","tools":[{"type":"vectorSearch","provider":"pinecone","index":"docs","namespace":"api","topK":10}]}}}'
```

### Create Quality Agent
```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer TOKEN" \
  -d '{"name":"Quality","config":{"version":2,"data":{"systemPrompt":"Quality","tools":[{"type":"vectorSearchWithReranking","provider":"pinecone","index":"docs","namespace":"support","topK":20,"topN":5}]}}}'
```

### Test Completion
```bash
curl -X POST http://localhost:4000/api/agents/123/completion \
  -H "Authorization: Bearer TOKEN" \
  -d '{"sessionId":"s1","prompt":"Search for authentication"}'
```

---

**For full documentation, see**: `/code/src/tools/INDEX.md`
