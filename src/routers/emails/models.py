"""Pydantic models for the Model A send primitive (POST /api/emails/send)."""
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class Recipient(BaseModel):
    """Exactly one of ``contact_id`` (preferred) or ``email`` (ad-hoc)."""
    contact_id: Optional[int] = Field(
        default=None,
        description="Preferred — enables personalization + dedup against the ledger.")
    email: Optional[str] = Field(
        default=None,
        description="Ad-hoc recipient when no contact record exists. Not deduped.")

    @model_validator(mode="after")
    def _exactly_one(self) -> "Recipient":
        if bool(self.contact_id) == bool(self.email):
            raise ValueError("Provide exactly one of recipient.contact_id or recipient.email")
        return self


class SendEmailRequest(BaseModel):
    campaign_id: int = Field(
        description="Required correlation tag — must reference an existing campaign.")
    template_id: int = Field(
        description="Immutable template to render. Never mutated to carry content.")
    variables: Dict[str, Any] = Field(
        default_factory=dict,
        description="Campaign-scoped content values injected into the template.")
    recipient: Recipient
    credential_id: int = Field(description="SES credential to send with.")
    dry_run: bool = Field(
        default=False,
        description="Validate required tokens and return without sending.")


class SendEmailResponse(BaseModel):
    campaign_id: int
    contact_id: Optional[int] = None
    tracking_id: Optional[str] = None
    # "sent" | "skipped_duplicate" | "validated"
    status: str
    event_id: Optional[int] = None
