"""
Pydantic request/response models for knowledge-base (vector store) access grants.
"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, model_validator
from datetime import datetime


class CreateVectorStoreGrantRequest(BaseModel):
    """Share a knowledge base with a group OR an individual, at a given role.

    Exactly one of accessGroupId / granteeEmail. role is 'read' (view) or
    'write' (ingest/edit).
    """
    index_name: str
    accessGroupId: Optional[int] = None
    granteeEmail: Optional[str] = None
    role: str = "read"

    @model_validator(mode="after")
    def _validate(self):
        if (self.accessGroupId is None) == (self.granteeEmail is None):
            raise ValueError("Provide exactly one of accessGroupId or granteeEmail")
        if self.role not in ("read", "write"):
            raise ValueError("role must be 'read' or 'write'")
        return self


class VectorStoreAccessGrantResponse(BaseModel):
    id: int
    owner_account_id: int
    index_name: str
    # Exactly one of these is set.
    access_group_id: Optional[int] = None
    grantee_account_id: Optional[int] = None
    label: str
    target_type: str  # 'group' | 'individual'
    role: str         # 'read' | 'write'
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedVectorStore(BaseModel):
    """A knowledge base shared with the caller (via direct or group grants)."""

    owner_account_id: int
    index_name: str
    can_write: bool
