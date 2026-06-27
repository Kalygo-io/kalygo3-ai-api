"""Pydantic models for the email_templates router."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime


class TemplateVariable(BaseModel):
    """Descriptor for a single variable slot in a template."""
    name: str = Field(description="Token name used in the template, e.g. 'first_name'")
    label: str = Field(description="Human-readable label shown in the UI")
    default: Optional[str] = Field(default="", description="Default value if not provided")
    required: bool = Field(default=False, description="Whether a non-empty value must be supplied at send time")
    scope: Literal["campaign", "contact", "system"] = Field(
        default="campaign",
        description=(
            "Where the value comes from at send time. 'campaign' — supplied in the "
            "send request `variables`; 'contact' — resolved from the contact record; "
            "'system' — injected by the backend (e.g. RATING_BASE_URL / tracking). "
            "Drives precise validation messages."),
    )


class CreateEmailTemplateRequest(BaseModel):
    name: str = Field(max_length=255)
    description: Optional[str] = None
    subject_template: str = Field(max_length=998,
        description="Subject line — may contain {{variable}} tokens")
    html_template: str = Field(
        description="Production-grade HTML email body with {{variable}} tokens")
    variables: Optional[List[TemplateVariable]] = Field(
        default=None,
        description="Ordered list of variable descriptors for the UI and the agent")


class UpdateEmailTemplateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    subject_template: Optional[str] = Field(default=None, max_length=998)
    html_template: Optional[str] = None
    variables: Optional[List[TemplateVariable]] = None


class EmailTemplateResponse(BaseModel):
    id: int
    account_id: int
    name: str
    description: Optional[str] = None
    subject_template: str
    html_template: str
    variables: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
