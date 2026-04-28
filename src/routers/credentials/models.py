"""
Pydantic models for the credentials router.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from src.db.service_name import ServiceName


# ── Legacy models (backward compatible) ──────────────────────────────────────

class CreateCredentialRequest(BaseModel):
    """Legacy request for creating API key credentials."""
    credential_type: ServiceName
    api_key: str


class UpdateCredentialRequest(BaseModel):
    """Legacy request for updating API key credentials."""
    api_key: str


class CredentialResponse(BaseModel):
    """Response model for credential metadata (no sensitive data)."""
    id: int
    credential_type: ServiceName
    auth_type: str = "api_key"
    credential_name: Optional[str] = None
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CredentialDetailResponse(BaseModel):
    """Response model with decrypted API key (legacy)."""
    id: int
    credential_type: ServiceName
    auth_type: str = "api_key"
    credential_name: Optional[str] = None
    api_key: str
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# ── Flexible models ──────────────────────────────────────────────────────────

class CreateFlexibleCredentialRequest(BaseModel):
    """
    Request for creating any type of credential.

    Examples:
    - API Key: {"credential_type": "OPENAI_API_KEY", "auth_type": "api_key", "credential_data": {"api_key": "sk-..."}}
    - Database: {"credential_type": "SUPABASE", "auth_type": "db_connection", "credential_data": {"host": "...", ...}}
    """
    credential_type: ServiceName
    auth_type: str = Field(default="api_key", description="Auth mechanism: api_key, db_connection, oauth, ssh_key, certificate, aws_access_key_pair")
    credential_name: Optional[str] = Field(default=None, description="Human-readable name for this credential (e.g. 'Production', 'Staging')")
    credential_data: Dict[str, Any] = Field(..., description="The credential data structure (varies by auth_type)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Non-sensitive metadata (notes, environment, etc.)")


class UpdateFlexibleCredentialRequest(BaseModel):
    """Request for updating any type of credential."""
    credential_name: Optional[str] = Field(default=None, description="Updated human-readable name")
    credential_data: Dict[str, Any] = Field(..., description="The new credential data")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Updated metadata")


class FlexibleCredentialDetailResponse(BaseModel):
    """Response model with full decrypted credential data."""
    id: int
    credential_type: ServiceName
    auth_type: str
    credential_name: Optional[str] = None
    credential_data: Dict[str, Any]
    created_at: str
    updated_at: str
    credential_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
