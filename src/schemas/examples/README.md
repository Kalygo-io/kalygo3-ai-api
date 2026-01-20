# Agent Config v2 Examples

This directory contains example agent configurations using the v2 schema.

## Examples Overview

### 1. Simple Chat Agent (`simple_chat_agent.v2.json`)

**Use Case:** Basic conversational AI without any tools.

**Features:**
- No knowledge bases or tools
- Pure LLM conversation
- Good for general Q&A, brainstorming, writing assistance

**When to use:**
- You don't need any external data
- Simple chat interface
- General-purpose assistant

**Try it:**
```bash
curl -X POST 'http://localhost:4000/api/agents' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: jwt=YOUR_JWT' \
  --data @src/schemas/examples/simple_chat_agent.v2.json
```

---

### 2. Support Agent (`support_agent.v2.json`)

**Use Case:** Customer support chatbot with access to FAQ and troubleshooting guides.

**Features:**
- 2 vector search tools (FAQ + Troubleshooting)
- Clear guidelines for escalation
- Empathetic and professional tone

**Tools:**
1. **FAQ Tool** - Common questions (topK: 5)
   - Account management
   - Billing issues
   - Basic technical questions

2. **Troubleshooting Tool** - Technical issues (topK: 8)
   - Error messages
   - Connectivity problems
   - Performance issues

**When to use:**
- Customer support automation
- First-line technical support
- Self-service help systems

**Customization tips:**
- Adjust `topK` based on answer complexity
- Add more namespaces for different product lines
- Update system prompt with specific escalation procedures

---

### 3. Technical Documentation Agent (`technical_documentation_agent.v2.json`)

**Use Case:** Developer documentation assistant with comprehensive API and SDK coverage.

**Features:**
- 4 vector search tools covering different aspects of documentation
- Technical, precise communication style
- Code examples and version-aware responses

**Tools:**
1. **API Reference Tool** (topK: 10)
   - REST API endpoints
   - Authentication methods
   - Request/response formats
   - Code examples

2. **SDK Guides Tool** (topK: 8)
   - Integration guides for multiple languages
   - Configuration examples
   - Best practices

3. **Tutorials Tool** (topK: 5)
   - Step-by-step guides
   - Common use cases
   - Workflow examples

4. **Migration Guides Tool** (topK: 6)
   - Version upgrade guides
   - Breaking changes
   - Migration code examples

**When to use:**
- Developer documentation portals
- API documentation search
- SDK support chatbot
- Internal developer tools

**Customization tips:**
- Add namespaces for specific API versions
- Include separate tools for different programming languages
- Adjust topK per tool based on typical query complexity

---

## Configuration Tips

### System Prompt Best Practices

**✅ Good:**
```json
{
  "systemPrompt": "You are a [ROLE]. Your job is to [PURPOSE].\n\nGuidelines:\n1. [Guideline 1]\n2. [Guideline 2]\n3. [Guideline 3]"
}
```

**❌ Bad:**
```json
{
  "systemPrompt": "Help users"
}
```

### Tool Description Best Practices

**✅ Good:**
```json
{
  "description": "REST API v3 documentation including endpoints, authentication, request/response formats, rate limits, and error codes. Includes Python, JavaScript, and cURL examples."
}
```

**❌ Bad:**
```json
{
  "description": "API docs"
}
```

### TopK Guidelines

| Content Type | Recommended topK | Reason |
|--------------|------------------|--------|
| FAQ / Quick answers | 3-5 | Need precise, focused results |
| General documentation | 8-10 | Balance between coverage and relevance |
| Research / Exploration | 15-20 | Comprehensive results needed |
| Troubleshooting | 5-8 | Need relevant error patterns |
| Code examples | 3-6 | Too many examples can be confusing |

## Testing Examples

### Validate an Example

```bash
python src/schemas/migrate_agent_config.py src/schemas/examples/support_agent.v2.json
```

### Create Agent from Example

```bash
# Load example file
AGENT_CONFIG=$(cat src/schemas/examples/support_agent.v2.json)

# Create agent
curl -X POST 'http://localhost:4000/api/agents' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: jwt=YOUR_JWT' \
  --data-raw "{
    \"name\": \"Support Agent\",
    \"description\": \"Customer support chatbot\",
    \"config\": $AGENT_CONFIG
  }"
```

### Test Agent Completion

```bash
# Use the agent_id from creation response
curl -X POST 'http://localhost:4000/api/agents/1/completion' \
  -H 'Content-Type: application/json' \
  -H 'Cookie: jwt=YOUR_JWT' \
  --data-raw '{
    "sessionId": "test-session-uuid",
    "prompt": "How do I reset my password?"
  }' \
  -N
```

## Creating Your Own Config

### Start from Template

1. Copy an example that's closest to your use case:
   ```bash
   cp src/schemas/examples/simple_chat_agent.v2.json my_agent.json
   ```

2. Modify the system prompt for your specific needs

3. Add tools if needed:
   ```json
   {
     "tools": [
       {
         "type": "vectorSearch",
         "provider": "pinecone",
         "index": "your-index-name",
         "namespace": "your-namespace",
         "description": "Clear description of what this contains",
         "topK": 10
       }
     ]
   }
   ```

4. Validate your config:
   ```bash
   python src/schemas/migrate_agent_config.py my_agent.json
   ```

### Common Patterns

**Pattern 1: Multi-Language Documentation**
```json
{
  "tools": [
    {
      "type": "vectorSearch",
      "namespace": "docs-python",
      "description": "Python-specific documentation and examples"
    },
    {
      "type": "vectorSearch",
      "namespace": "docs-javascript",
      "description": "JavaScript/Node.js-specific documentation and examples"
    }
  ]
}
```

**Pattern 2: Versioned Documentation**
```json
{
  "tools": [
    {
      "type": "vectorSearch",
      "namespace": "api-v3",
      "description": "Current API v3 documentation (recommended)"
    },
    {
      "type": "vectorSearch",
      "namespace": "api-v2-legacy",
      "description": "Legacy API v2 documentation (deprecated, use for migration only)"
    }
  ]
}
```

**Pattern 3: Tiered Support**
```json
{
  "tools": [
    {
      "type": "vectorSearch",
      "namespace": "tier1-faq",
      "description": "First-line support: common questions and quick fixes",
      "topK": 3
    },
    {
      "type": "vectorSearch",
      "namespace": "tier2-technical",
      "description": "Second-line support: detailed technical solutions",
      "topK": 8
    }
  ]
}
```

## Migration from v1

If you have existing v1 configs, migrate them:

```bash
python src/schemas/migrate_agent_config.py old_config_v1.json new_config_v2.json
```

See `../AGENT_CONFIG_V2_GUIDE.md` for detailed migration instructions.

## Further Reading

- **Schema Definition:** `../agent_config.v2.json`
- **Migration Guide:** `../AGENT_CONFIG_V2_GUIDE.md`
- **Migration Tool:** `../migrate_agent_config.py`
