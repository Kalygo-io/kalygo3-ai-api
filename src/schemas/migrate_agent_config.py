"""
Agent Config Migration Utility

Migrate agent configs from v1 to v2 schema.
"""
from typing import Dict, Any, Optional
import json
from pathlib import Path


def migrate_v1_to_v2(v1_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert agent config from v1 to v2 schema.
    
    v1 schema uses 'knowledgeBases' array
    v2 schema uses 'tools' array with typed tools
    
    Args:
        v1_config: Agent config in v1 format
        
    Returns:
        Agent config in v2 format
        
    Example:
        >>> v1 = {
        ...     "schema": "agent_config",
        ...     "version": 1,
        ...     "data": {
        ...         "systemPrompt": "You are helpful",
        ...         "knowledgeBases": [{
        ...             "provider": "pinecone",
        ...             "index": "my-index",
        ...             "namespace": "docs"
        ...         }]
        ...     }
        ... }
        >>> v2 = migrate_v1_to_v2(v1)
        >>> v2["version"]
        2
        >>> v2["data"]["tools"][0]["type"]
        'vectorSearch'
    """
    # Validate input is v1
    if v1_config.get("version") != 1:
        raise ValueError(f"Expected version 1, got {v1_config.get('version')}")
    
    if v1_config.get("schema") != "agent_config":
        raise ValueError(f"Expected schema 'agent_config', got {v1_config.get('schema')}")
    
    # Create v2 base structure
    v2_config = {
        "schema": "agent_config",
        "version": 2,
        "data": {
            "systemPrompt": v1_config["data"]["systemPrompt"]
        }
    }
    
    # Convert knowledgeBases to vectorSearch tools
    knowledge_bases = v1_config["data"].get("knowledgeBases", [])
    
    if knowledge_bases:
        v2_config["data"]["tools"] = []
        
        for kb in knowledge_bases:
            # Create vectorSearch tool from knowledge base
            tool = {
                "type": "vectorSearch",
                "provider": kb["provider"],
                "index": kb["index"],
                "namespace": kb["namespace"]
            }
            
            # Copy optional description
            if "description" in kb:
                tool["description"] = kb["description"]
            
            # Default topK to 10 if not specified
            # v1 didn't have this field, but v2 does
            tool["topK"] = 10
            
            v2_config["data"]["tools"].append(tool)
    
    return v2_config


def migrate_v2_to_v1(v2_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert agent config from v2 back to v1 schema (for backwards compatibility).
    
    Only vectorSearch tools can be converted back to knowledgeBases.
    Other tool types will be lost in the conversion.
    
    Args:
        v2_config: Agent config in v2 format
        
    Returns:
        Agent config in v1 format
        
    Warning:
        This is a lossy conversion. Only vectorSearch tools are preserved.
    """
    # Validate input is v2
    if v2_config.get("version") != 2:
        raise ValueError(f"Expected version 2, got {v2_config.get('version')}")
    
    if v2_config.get("schema") != "agent_config":
        raise ValueError(f"Expected schema 'agent_config', got {v2_config.get('schema')}")
    
    # Create v1 base structure
    v1_config = {
        "schema": "agent_config",
        "version": 1,
        "data": {
            "systemPrompt": v2_config["data"]["systemPrompt"]
        }
    }
    
    # Convert vectorSearch tools to knowledgeBases
    tools = v2_config["data"].get("tools", [])
    knowledge_bases = []
    
    for tool in tools:
        # Only convert vectorSearch tools
        if tool.get("type") == "vectorSearch":
            kb = {
                "provider": tool["provider"],
                "index": tool["index"],
                "namespace": tool["namespace"]
            }
            
            # Copy optional description
            if "description" in tool:
                kb["description"] = tool["description"]
            
            # Note: topK is dropped as v1 doesn't support it
            
            knowledge_bases.append(kb)
    
    if knowledge_bases:
        v1_config["data"]["knowledgeBases"] = knowledge_bases
    
    return v1_config


def load_and_migrate_file(input_path: str, output_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load a v1 config from a file, migrate to v2, and optionally save.
    
    Args:
        input_path: Path to v1 config JSON file
        output_path: Optional path to save v2 config (defaults to input_path with .v2.json suffix)
        
    Returns:
        Migrated v2 config
    """
    # Load v1 config
    with open(input_path, 'r') as f:
        v1_config = json.load(f)
    
    # Migrate to v2
    v2_config = migrate_v1_to_v2(v1_config)
    
    # Save if output path provided
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(v2_config, f, indent=2)
        print(f"✅ Migrated config saved to: {output_path}")
    elif output_path is None and input_path.endswith('.json'):
        # Auto-generate output path
        output_path = input_path.replace('.json', '.v2.json')
        with open(output_path, 'w') as f:
            json.dump(v2_config, f, indent=2)
        print(f"✅ Migrated config saved to: {output_path}")
    
    return v2_config


def validate_v2_config(config: Dict[str, Any]) -> bool:
    """
    Validate a v2 config against the schema.
    
    Args:
        config: Agent config in v2 format
        
    Returns:
        True if valid
        
    Raises:
        jsonschema.ValidationError if invalid
    """
    try:
        import jsonschema
    except ImportError:
        print("⚠️  jsonschema not installed. Run: pip install jsonschema")
        return False
    
    # Load v2 schema
    schema_path = Path(__file__).parent / "agent_config.v2.json"
    with open(schema_path, 'r') as f:
        schema = json.load(f)
    
    # Validate
    try:
        jsonschema.validate(config, schema)
        print("✅ Config is valid!")
        return True
    except jsonschema.ValidationError as e:
        print(f"❌ Validation error: {e.message}")
        print(f"   Path: {' -> '.join(str(p) for p in e.path)}")
        raise


def main():
    """CLI for migrating agent configs."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python migrate_agent_config.py <input_v1_config.json> [output_v2_config.json]")
        print("\nExamples:")
        print("  # Migrate and auto-save to .v2.json")
        print("  python migrate_agent_config.py my_agent.json")
        print()
        print("  # Migrate and save to specific file")
        print("  python migrate_agent_config.py old_config.json new_config.json")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        # Load and migrate
        print(f"📖 Loading v1 config from: {input_path}")
        v2_config = load_and_migrate_file(input_path, output_path)
        
        # Validate
        print("\n🔍 Validating v2 config...")
        validate_v2_config(v2_config)
        
        # Show summary
        print("\n📊 Migration Summary:")
        print(f"   Version: 1 → 2")
        
        tools_count = len(v2_config["data"].get("tools", []))
        print(f"   Tools: {tools_count}")
        
        if tools_count > 0:
            for i, tool in enumerate(v2_config["data"]["tools"], 1):
                print(f"     {i}. {tool['type']} ({tool['provider']}/{tool['index']}/{tool['namespace']})")
        
        print("\n✨ Migration complete!")
        
    except FileNotFoundError:
        print(f"❌ Error: File not found: {input_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in {input_path}")
        print(f"   {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
