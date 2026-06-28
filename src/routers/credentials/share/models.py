"""
Pydantic request/response models for credential access grants.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, model_validator


class CreateCredentialGrantRequest(BaseModel):
    """
    Share a credential with EITHER an access group OR an individual (by email).
    Exactly one of accessGroupId / granteeEmail must be provided.
    """
    accessGroupId: Optional[int] = None
    granteeEmail: Optional[str] = None

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if (self.accessGroupId is None) == (self.granteeEmail is None):
            raise ValueError("Provide exactly one of accessGroupId or granteeEmail")
        return self


class CredentialGrantResponse(BaseModel):
    id: int
    credential_id: int
    # The target: exactly one of these is set.
    access_group_id: Optional[int] = None
    grantee_account_id: Optional[int] = None
    # Human-readable label for display: group name, or grantee email.
    label: str
    # 'group' | 'individual'
    target_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
