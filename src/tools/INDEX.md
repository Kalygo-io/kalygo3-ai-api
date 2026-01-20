# Tool System - Complete Documentation Index

Welcome to the Agent Tool System! This index helps you navigate all the documentation.

## 🚀 Quick Start

**New to the tool system?** Start here:
1. [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick reference card ⭐
2. [README.md](README.md) - Overview and basic usage
3. [TESTING_GUIDE.md](TESTING_GUIDE.md) - Test the system
4. [examples.py](examples.py) - See code examples

## 📚 Documentation Files

### Core Documentation

#### [QUICK_REFERENCE.md](QUICK_REFERENCE.md) ⭐
**Purpose**: Quick reference card for both tool types  
**Topics**:
- Side-by-side tool comparison
- Agent config examples
- When to use which tool
- Common issues and solutions
- Testing commands

**When to read**: Need a quick reminder, or choosing between tools

---

#### [README.md](README.md)
**Purpose**: Main documentation for the tool system  
**Topics**:
- System overview and architecture
- Usage examples (v1 and v2 configs)
- Available tools (vectorSearch)
- Adding new tools (step-by-step guide)
- Tool builder signature
- Error handling
- Testing
- Performance and security

**When to read**: First time using the system, or as a reference

---

#### [ARCHITECTURE.md](ARCHITECTURE.md)
**Purpose**: Deep dive into system architecture  
**Topics**:
- High-level component diagrams
- Data flow diagrams
- Tool lifecycle
- File structure
- Dependencies
- Extension points
- Security model
- Performance characteristics

**When to read**: Understanding how the system works internally, or designing new features

---

#### [TESTING_GUIDE.md](TESTING_GUIDE.md)
**Purpose**: Practical testing instructions  
**Topics**:
- API testing with curl
- Creating v2 agents
- Testing v1 backwards compatibility
- Log interpretation
- Python REPL testing
- Error handling tests
- Integration test script
- Troubleshooting

**When to read**: Testing new features, debugging issues, or verifying functionality

---

### Code Files

#### [examples.py](examples.py)
**Purpose**: Runnable code examples  
**Topics**:
- List available tools
- Create single tool
- Create tools from v2 config
- Create tools from v1 config
- Error handling
- Register custom tools
- Tool configuration examples
- Complete agent configs

**When to read**: Learning by example, or copying patterns into your code

**Run it**:
```bash
python -m src.tools.examples
```

---

### Source Code

#### [\_\_init\_\_.py](__init__.py)
**Purpose**: Package entry point  
**Exports**:
- `create_tool_from_config()`
- `create_tools_from_agent_config()`
- `ToolRegistry`
- `register_tool_type()`
- `get_tool_builder()`

**Import example**:
```python
from src.tools import create_tools_from_agent_config
```

---

#### [registry.py](registry.py)
**Purpose**: Tool type registry  
**Key class**: `ToolRegistry`  
**Methods**:
- `register(type, builder)` - Register a tool type
- `get_builder(type)` - Get builder function
- `list_types()` - List all registered types
- `is_registered(type)` - Check if type exists

**When to modify**: Never (unless adding registry features)

---

#### [factory.py](factory.py)
**Purpose**: Tool creation from configs  
**Key functions**:
- `create_tool_from_config()` - Create single tool
- `create_tools_from_agent_config()` - Create all tools from agent config

**Features**:
- Automatic v1 → v2 conversion
- Error handling
- Detailed logging

**When to modify**: Never (unless changing tool creation logic)

---

#### [auto_register.py](auto_register.py)
**Purpose**: Auto-register all tools on import  
**Function**: `register_all_tools()`

**When to modify**: When adding a new tool type (add one line)

---

#### [vector_search.py](vector_search.py)
**Purpose**: Fast vector search tool implementation  
**Function**: `create_vector_search_tool()`

**Supports**:
- Pinecone vector database
- Embedding API integration
- JWT and API key auth
- Configurable topK

**When to modify**: When extending basic vector search features

---

#### [vector_search_with_reranking.py](vector_search_with_reranking.py)
**Purpose**: High-quality vector search with re-ranking  
**Function**: `create_vector_search_with_reranking_tool()`

**Supports**:
- Two-stage retrieval (similarity + re-ranking)
- Pinecone vector database
- Embedding API and Reranker API integration
- JWT and API key auth
- Configurable topK and topN
- Graceful fallback if reranker unavailable

**When to modify**: When extending re-ranking features

---

## 📖 Reading Paths

### Path 1: I want to USE the tool system

1. [README.md](README.md) - Overview and usage
2. [examples.py](examples.py) - Code examples
3. [TESTING_GUIDE.md](TESTING_GUIDE.md) - Test your implementation

### Path 2: I want to ADD a new tool

1. [README.md](README.md) - "Adding New Tools" section
2. [ARCHITECTURE.md](ARCHITECTURE.md) - "Extension Points" section
3. [vector_search.py](vector_search.py) - Example implementation
4. [auto_register.py](auto_register.py) - Add registration

### Path 3: I want to UNDERSTAND the architecture

1. [ARCHITECTURE.md](ARCHITECTURE.md) - Complete architecture
2. [factory.py](factory.py) - Tool creation logic
3. [registry.py](registry.py) - Registry implementation
4. [vector_search.py](vector_search.py) - Example tool

### Path 4: I'm DEBUGGING an issue

1. [TESTING_GUIDE.md](TESTING_GUIDE.md) - "Troubleshooting" section
2. [README.md](README.md) - "Error Handling" section
3. Check server logs for `[TOOL FACTORY]`, `[TOOL REGISTRY]` messages
4. [examples.py](examples.py) - Run example 5 (error handling)

### Path 5: I'm MIGRATING from v1 to v2

1. [README.md](README.md) - "Backwards Compatibility" section
2. [TESTING_GUIDE.md](TESTING_GUIDE.md) - v1 compatibility tests
3. [../schemas/AGENT_CONFIG_V2_GUIDE.md](../schemas/AGENT_CONFIG_V2_GUIDE.md) - Migration guide

## 🎯 Common Tasks

### Create an agent with tools

**See**: [TESTING_GUIDE.md](TESTING_GUIDE.md) - "Quick Test: Create Agent with v2 Config"

```bash
curl -X POST http://localhost:4000/api/agents \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "...", "config": {...}}'
```

### Add a new tool type

**See**: [README.md](README.md) - "Adding New Tools"

1. Create `src/tools/my_tool.py`
2. Register in `auto_register.py`
3. Add schema to `agent_config.v2.json`
4. Test it!

### Debug tool creation

**See**: [TESTING_GUIDE.md](TESTING_GUIDE.md) - "Troubleshooting"

```python
# Check registry
from src.tools import ToolRegistry
print(ToolRegistry.list_types())

# Check logs
# Look for: [TOOL FACTORY], [TOOL REGISTRY], [VECTOR SEARCH TOOL]
```

### Test backwards compatibility

**See**: [TESTING_GUIDE.md](TESTING_GUIDE.md) - "Verify v1 Backwards Compatibility"

Create agent with v1 config (`knowledgeBases`) and verify it works.

## 📦 Related Documentation

### Outside `/code/src/tools/`

- [/code/src/schemas/AGENT_CONFIG_V2_GUIDE.md](../schemas/AGENT_CONFIG_V2_GUIDE.md) - v2 schema guide
- [/code/src/schemas/agent_config.v2.json](../schemas/agent_config.v2.json) - v2 JSON schema
- [/code/src/schemas/agent_config.v1.json](../schemas/agent_config.v1.json) - v1 JSON schema
- [/code/src/schemas/examples/](../schemas/examples/) - Example agent configs
- [/code/TOOL_SYSTEM_SUMMARY.md](../../TOOL_SYSTEM_SUMMARY.md) - Implementation summary
- [/code/src/routers/agents/completion.py](../routers/agents/completion.py) - Integration point

## 🔍 Search Tips

### Find by topic

- **Usage**: README.md, examples.py
- **Architecture**: ARCHITECTURE.md
- **Testing**: TESTING_GUIDE.md
- **Migration**: README.md ("Backwards Compatibility"), ../schemas/AGENT_CONFIG_V2_GUIDE.md
- **Debugging**: TESTING_GUIDE.md ("Troubleshooting")
- **Adding tools**: README.md ("Adding New Tools"), ARCHITECTURE.md ("Extension Points")

### Find by file type

- **Documentation**: README.md, ARCHITECTURE.md, TESTING_GUIDE.md, INDEX.md
- **Examples**: examples.py
- **Source**: __init__.py, registry.py, factory.py, auto_register.py, vector_search.py

### Find by keyword

| Keyword | Files |
|---------|-------|
| register | registry.py, auto_register.py, README.md |
| create | factory.py, vector_search.py, examples.py |
| config | factory.py, README.md, TESTING_GUIDE.md |
| v1 / v2 | factory.py, README.md, TESTING_GUIDE.md |
| error | factory.py, README.md, TESTING_GUIDE.md |
| test | TESTING_GUIDE.md, examples.py |
| architecture | ARCHITECTURE.md |
| security | ARCHITECTURE.md, README.md |
| performance | ARCHITECTURE.md, README.md |

## 📊 File Summary

| File | Lines | Purpose |
|------|-------|---------|
| QUICK_REFERENCE.md | ~180 | Quick reference card ⭐ |
| README.md | ~650 | Main documentation |
| ARCHITECTURE.md | ~900 | Architecture deep dive |
| TESTING_GUIDE.md | ~500 | Testing instructions |
| examples.py | ~500 | Code examples |
| INDEX.md | ~400 | This file |
| __init__.py | ~20 | Package entry |
| registry.py | ~76 | Tool registry |
| factory.py | ~180 | Tool factory |
| auto_register.py | ~30 | Auto-registration |
| vector_search.py | ~170 | Vector search tool |
| vector_search_with_reranking.py | ~337 | Vector search with re-ranking |

**Total**: ~3,900+ lines of documentation and code

## 🎓 Learning Path

### Beginner
1. Read README.md overview
2. Look at examples.py examples 7-8
3. Run TESTING_GUIDE.md quick test
4. ✅ You can now use the tool system!

### Intermediate
1. Read README.md "Adding New Tools"
2. Study vector_search.py implementation
3. Look at ARCHITECTURE.md "Tool Builder Template"
4. ✅ You can now create custom tools!

### Advanced
1. Read ARCHITECTURE.md completely
2. Study factory.py implementation
3. Study registry.py implementation
4. Read security and performance sections
5. ✅ You understand the system deeply!

## 💡 Tips

- **Bookmark this INDEX**: It's your starting point for everything
- **Check logs first**: Most issues are visible in `[TOOL FACTORY]` logs
- **Start with examples**: examples.py has runnable code
- **Test incrementally**: Use TESTING_GUIDE.md steps
- **v1 still works**: No need to migrate existing agents immediately

## 🆘 Getting Help

1. **Check logs**: Look for `[TOOL FACTORY]`, `[TOOL REGISTRY]`, `[VECTOR SEARCH TOOL]`
2. **Run examples**: `python -m src.tools.examples`
3. **Check TESTING_GUIDE.md**: Troubleshooting section
4. **Check README.md**: Error handling section
5. **Check ARCHITECTURE.md**: Understanding system behavior

## ✅ Quick Reference

### Import tools
```python
from src.tools import create_tools_from_agent_config
```

### Create tools
```python
tools = await create_tools_from_agent_config(
    agent_config=config,
    account_id=123,
    db=db,
    auth_token=token
)
```

### Register new tool
```python
# In auto_register.py
register_tool_type("myTool", create_my_tool)
```

### Check registry
```python
from src.tools import ToolRegistry
print(ToolRegistry.list_types())
```

---

**Last Updated**: 2026-01-19  
**Version**: 1.0  
**Status**: Production Ready ✅
