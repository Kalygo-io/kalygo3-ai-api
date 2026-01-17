"""
JSON Schema validation utilities for the Kalygo platform.
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
import jsonschema
from jsonschema import ValidationError, Draft202012Validator


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


def validate_against_schema(
    data: Dict[str, Any],
    schema_name: str,
    version: int
) -> None:
    """
    Validate data against a JSON schema.
    
    Args:
        data: The data dictionary to validate
        schema_name: Name of the schema (e.g., 'agent_config')
        version: Version number of the schema
        
    Raises:
        ValidationError: If the data doesn't match the schema
        FileNotFoundError: If the schema file doesn't exist
    """
    schema = load_schema(schema_name, version)
    validator = Draft202012Validator(schema)
    
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
