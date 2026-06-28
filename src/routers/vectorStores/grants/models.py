"""
Pydantic request/response models for knowledge-base (vector store) access grants.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class CreateVectorStoreGrantRequest(BaseModel):
    index_name: str
    accessGroupId: int


class VectorStoreAccessGrantResponse(BaseModel):
    id: int
    owner_account_id: int
    index_name: str
    access_group_id: int
    access_group_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SharedVectorStore(BaseModel):
    """A knowledge base shared with the caller via access-group membership."""

    owner_account_id: int
    index_name: str
    can_write: bool
