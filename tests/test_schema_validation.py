"""
Tests for JSON schema validation (src/schemas).

Locks in the behavior of validate_against_schema after removing the deprecated
jsonschema RefResolver: valid configs pass, invalid configs raise, and internal
`#/$defs/...` references still resolve and validate nested structures.
"""
import pytest
from jsonschema import ValidationError

from src.schemas import validate_against_schema, load_schema


def test_valid_agent_config_passes():
    config = {
        "schema": "agent_config",
        "version": 4,
        "data": {"systemPrompt": "You are a helpful assistant."},
    }
    # Should not raise.
    validate_against_schema(config, "agent_config", 4)


def test_missing_required_field_raises():
    with pytest.raises(ValidationError):
        validate_against_schema({}, "agent_config", 4)


def test_internal_ref_is_resolved_and_validated():
    """A nested object validated via an internal $ref (#/$defs/modelConfig)
    must surface the nested constraint error — proving the ref resolved."""
    config = {
        "schema": "agent_config",
        "version": 4,
        # model omits the required "model" key; this lives behind a $ref.
        "data": {"systemPrompt": "hi", "model": {"provider": "x"}},
    }
    with pytest.raises(ValidationError) as exc_info:
        validate_against_schema(config, "agent_config", 4)
    assert "model" in str(exc_info.value)


def test_missing_schema_file_raises():
    with pytest.raises(FileNotFoundError):
        load_schema("does_not_exist", 99)
