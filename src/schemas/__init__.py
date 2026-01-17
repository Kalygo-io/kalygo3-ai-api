"""
JSON Schema validation utilities for the Kalygo platform.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
import jsonschema
from jsonschema import ValidationError, Draft202012Validator, RefResolver


def load_schema(schema_name: str, version: int) -> Dict[str, Any]:
    """
    Load a JSON schema file from the schemas directory.
    
    Args:
        schema_name: Name of the schema (e.g., 'agent_config')
        version: Version number of the schema
        
    Returns:
        Dictionary containing the schema definition
        
    Raises:
        FileNotFoundError: If the schema file doesn't exist
        json.JSONDecodeError: If the schema file is invalid JSON
    """
    # Get the directory where this file is located
    current_dir = Path(__file__).parent
    schema_file = current_dir / f"{schema_name}.v{version}.json"
    
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    
    with open(schema_file, 'r') as f:
        return json.load(f)


def _resolve_file_reference(uri: str, current_dir: Path) -> Dict[str, Any]:
    """
    Resolve a file reference URI to a schema dictionary.
    Handles both relative paths (./filename.json) and absolute file:// URIs.
    
    Args:
        uri: The URI to resolve (e.g., "./agent_config.v1.json" or "file:///path/to/file.json")
        current_dir: The directory to resolve relative paths from
        
    Returns:
        Dictionary containing the schema definition
        
    Raises:
        FileNotFoundError: If the referenced file doesn't exist
    """
    # Handle relative file paths (most common case)
    if uri.startswith("./"):
        file_path = current_dir / uri.replace("./", "")
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        raise FileNotFoundError(f"Referenced schema file not found: {file_path}")
    
    # Handle bare filenames (no ./ prefix but not a URL)
    if not uri.startswith("http") and not uri.startswith("file://") and "/" not in uri:
        # Check if it's a schema file in the current directory
        file_path = current_dir / uri
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        raise FileNotFoundError(f"Referenced schema file not found: {file_path}")
    
    # Handle file:// URIs
    if uri.startswith("file://"):
        file_path = Path(uri.replace("file://", ""))
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)
        raise FileNotFoundError(f"Referenced schema file not found: {file_path}")
    
    # Handle $id-based references (https://kalygo.example/schemas/...)
    if uri.startswith("https://kalygo.example/schemas/"):
        # Extract filename from URI - handle both .schema.json and .v1.json patterns
        filename = uri.replace("https://kalygo.example/schemas/", "")
        # Remove .schema.json suffix if present
        if filename.endswith(".schema.json"):
            filename = filename.replace(".schema.json", "")
        # Try common patterns
        for pattern in [f"{filename}.json", f"{filename}.v1.json"]:
            schema_file = current_dir / pattern
            if schema_file.exists():
                with open(schema_file, 'r') as f:
                    return json.load(f)
        raise FileNotFoundError(f"Referenced schema not found: {uri}")
    
    raise FileNotFoundError(f"Unsupported URI format: {uri}")


def validate_against_schema(
    data: Dict[str, Any],
    schema_name: str,
    version: int
) -> None:
    """
    Validate data against a JSON schema.
    Supports $ref to external schema files.
    
    Args:
        data: The data dictionary to validate
        schema_name: Name of the schema (e.g., 'agent_config')
        version: Version number of the schema
        
    Raises:
        ValidationError: If the data doesn't match the schema
        FileNotFoundError: If the schema file doesn't exist
    """
    current_dir = Path(__file__).parent
    schema = load_schema(schema_name, version)
    
    # Create a custom resolver that handles file references
    # Use a file:// base URI for the current directory
    base_uri = f"file://{current_dir.absolute()}/"
    
    # Create resolver with custom handler for file references
    store = {}
    
    def resolve(uri: str):
        """Resolve a URI to a schema."""
        # Normalize the URI - handle relative paths
        normalized_uri = uri
        
        # If it's a relative path, resolve it relative to current_dir
        if uri.startswith("./") or (not uri.startswith("http") and not uri.startswith("file://") and "/" not in uri):
            # It's a relative file reference
            normalized_uri = uri
        
        # Check if already resolved (use normalized URI as key)
        if normalized_uri in store:
            return store[normalized_uri]
        
        # Resolve the reference
        resolved = _resolve_file_reference(normalized_uri, current_dir)
        
        # Store by the resolved URI
        store[normalized_uri] = resolved
        
        # Also store by the schema's $id if it has one (so future references work)
        if "$id" in resolved:
            store[resolved["$id"]] = resolved
        
        # Also store by original URI if different
        if normalized_uri != uri:
            store[uri] = resolved
        
        return resolved
    
    # Pre-load and register the main schema and any referenced schemas by their $id
    # This prevents the resolver from trying to fetch them as URLs
    store[schema.get("$id", base_uri)] = schema
    
    # Also register common schema files by their $id patterns
    # Load agent_config schema if it exists and register it
    try:
        config_schema = load_schema("agent_config", 1)
        if "$id" in config_schema:
            store[config_schema["$id"]] = config_schema
        # Also register by filename pattern
        store["./agent_config.v1.json"] = config_schema
        store["agent_config.v1.json"] = config_schema
    except FileNotFoundError:
        pass  # Config schema might not exist, that's okay
    
    # Create resolver with base URI pointing to the schemas directory
    resolver = RefResolver(base_uri, schema, store=store)
    
    # Override the resolver's resolve_from_url to use our custom resolver
    original_resolve_from_url = resolver.resolve_from_url
    
    def custom_resolve_from_url(url: str):
        """Custom resolver that handles file references before falling back to default."""
        # Check store first
        if url in store:
            return store[url]
        
        # Try our custom resolver
        try:
            resolved = resolve(url)
            return resolved
        except FileNotFoundError:
            pass
        
        # If it's a kalygo.example URL, try to resolve it as a local file
        if url.startswith("https://kalygo.example/schemas/"):
            try:
                resolved = resolve(url)
                return resolved
            except FileNotFoundError:
                pass
        
        # Fall back to original resolver (but this will likely fail for our use case)
        try:
            return original_resolve_from_url(url)
        except Exception:
            # Last resort: try resolving as a file path
            try:
                return resolve(url)
            except FileNotFoundError:
                raise FileNotFoundError(f"Could not resolve schema reference: {url}")
    
    resolver.resolve_from_url = custom_resolve_from_url
    
    # Create validator with resolver
    validator = Draft202012Validator(schema, resolver=resolver)
    
    errors = list(validator.iter_errors(data))
    if errors:
        error_messages = []
        for error in errors:
            error_path = " -> ".join(str(p) for p in error.path)
            error_msg = f"{error_path}: {error.message}" if error.path else error.message
            error_messages.append(error_msg)
        
        raise ValidationError(
            f"Validation failed for schema '{schema_name}' v{version}:\n" +
            "\n".join(f"  - {msg}" for msg in error_messages)
        )
