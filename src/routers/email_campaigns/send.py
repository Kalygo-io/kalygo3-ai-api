"""
Direct campaign dispatch endpoint — bypasses tool-approval workflow.

POST /api/email-campaigns/{campaign_id}/send

Looks up the campaign's linked template and contact list, renders the
template per contact (substituting {{variable}} tokens with contact fields),
generates a unique tracking_id per contact for rating/open correlation,
sends all emails in one call, and records an EmailEvent per contact.
"""
import logging
import os
import re
import uuid as _uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional

from src.deps import db_dependency, auth_dependency
from src.db.models import (
    Contact,
    ContactListMember,
    Credential,
    EmailCampaign,
    EmailEvent,
    EmailTemplate,
)
from src.routers.credentials.encryption import decrypt_credential_data
from src.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter()

_TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://127.0.0.1:4000")


# ── Request / Response Models ────────────────────────────────────────────────

class CampaignSendRequest(BaseModel):
    credential_id: int = Field(description="ID of the SES credential to use for sending")
    dry_run: bool = Field(default=False, description="If true, validates everything but doesn't send")


class SendError(BaseModel):
    contact_id: int
    email: str
    reason: str


class CampaignSendResponse(BaseModel):
    campaign_id: int
    total_contacts: int
    sent: int
    failed: int
    errors: list[SendError]
    batch_id: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _render_template(template_str: str, variables: dict[str, str]) -> str:
    """Replace {{var}} and {{ var }} tokens with values from the variables dict."""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replacer, template_str)


def _inject_tracking_pixel(html: str, tracking_id: str) -> str:
    """Inject a 1x1 invisible open-tracking pixel just before </body>."""
    pixel = (
        f'<img src="{_TRACKING_BASE_URL}/t/o/{tracking_id}" '
        f'width="1" height="1" style="display:none;border:0;" alt="" />'
    )
    if "</body>" in html.lower():
        return re.sub(r"</body>", f"{pixel}\n</body>", html, count=1, flags=re.IGNORECASE)
    return html + pixel


def _strip_html_tags(html: str) -> str:
    """Strip HTML tags and collapse whitespace for a plain-text fallback."""
    text = re.sub(r"<(br\s*/?|/?(p|div|tr|li|h[1-6])[^>]*)>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_contact_variables(contact: Contact, tracking_id: str) -> dict[str, str]:
    """Build the variable substitution map for a given contact."""
    rating_base = f"{_TRACKING_BASE_URL}/t/r/{tracking_id}"
    return {
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "name": contact.name or "",
        "email": contact.email or "",
        "FIRST_NAME": contact.first_name or "",
        "LAST_NAME": contact.last_name or "",
        "NAME": contact.name or "",
        "EMAIL": contact.email or "",
        "RATING_BASE_URL": rating_base,
        "rating_base_url": rating_base,
        "tracking_id": tracking_id,
        "TRACKING_ID": tracking_id,
    }


def _send_ses_html_email(ses_cfg: dict, to_email: str, subject: str, html_body: str) -> str:
    """Send HTML email via boto3/SES. Returns the SES MessageId."""
    import boto3

    plain_fallback = _strip_html_tags(html_body)
    client = boto3.client(
        "ses",
        region_name=ses_cfg["aws_region"],
        aws_access_key_id=ses_cfg["aws_access_key_id"],
        aws_secret_access_key=ses_cfg["aws_secret_access_key"],
    )
    response = client.send_email(
        Source=ses_cfg["from_email"],
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": plain_fallback, "Charset": "UTF-8"},
            },
        },
    )
    return response.get("MessageId", "unknown")


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/send", response_model=CampaignSendResponse)
@limiter.limit("10/minute")
async def send_campaign(
    campaign_id: int,
    body: CampaignSendRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """
    Send a campaign's email template to every contact in its linked list.

    Generates a unique tracking_id per contact so rating and open events
    can be correlated back to the specific contact-campaign pair.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    # ── Load and validate campaign ───────────────────────────────────────
    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    if not campaign.email_template_id:
        raise HTTPException(
            status_code=422, detail="Campaign has no email template linked")
    if not campaign.contact_list_id:
        raise HTTPException(
            status_code=422, detail="Campaign has no contact list linked")

    # ── Load template ────────────────────────────────────────────────────
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == campaign.email_template_id,
        EmailTemplate.account_id == account_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Linked email template not found")

    # ── Load contacts from the list ──────────────────────────────────────
    members = (
        db.query(ContactListMember)
        .filter(
            ContactListMember.contact_list_id == campaign.contact_list_id,
            ContactListMember.account_id == account_id,
        )
        .all()
    )
    if not members:
        raise HTTPException(status_code=422, detail="Contact list has no members")

    contact_ids = [m.contact_id for m in members]
    contacts = (
        db.query(Contact)
        .filter(Contact.id.in_(contact_ids), Contact.account_id == account_id)
        .all()
    )
    if not contacts:
        raise HTTPException(status_code=422, detail="No valid contacts found in list")

    # ── Load and decrypt credential ──────────────────────────────────────
    credential = db.query(Credential).filter(
        Credential.id == body.credential_id,
        Credential.account_id == account_id,
    ).first()
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    try:
        cred_data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        logger.error("Failed to decrypt credential %d: %s", body.credential_id, e)
        raise HTTPException(status_code=500, detail="Failed to decrypt credential")

    required_fields = ["aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"]
    missing = [k for k in required_fields if not cred_data.get(k)]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Credential is missing required SES fields: {', '.join(missing)}")

    # ── Generate batch_id ────────────────────────────────────────────────
    batch_id = str(_uuid.uuid4())

    # ── Dry run: validate only ───────────────────────────────────────────
    if body.dry_run:
        return CampaignSendResponse(
            campaign_id=campaign.id,
            total_contacts=len(contacts),
            sent=0,
            failed=0,
            errors=[],
            batch_id=batch_id,
        )

    # ── Send to each contact ─────────────────────────────────────────────
    sent_count = 0
    errors: list[SendError] = []
    from_email = cred_data["from_email"]
    sender_domain = from_email.split("@")[1] if "@" in from_email else None

    for contact in contacts:
        tracking_id = str(_uuid.uuid4())
        variables = _build_contact_variables(contact, tracking_id)

        rendered_subject = _render_template(template.subject_template, variables)
        rendered_html = _render_template(template.html_template, variables)
        rendered_html = _inject_tracking_pixel(rendered_html, tracking_id)

        try:
            message_id = _send_ses_html_email(
                cred_data, contact.email, rendered_subject, rendered_html
            )
        except Exception as exc:
            logger.warning(
                "Campaign %d: failed to send to %s: %s",
                campaign_id, contact.email, exc,
            )
            errors.append(SendError(
                contact_id=contact.id,
                email=contact.email,
                reason=str(exc),
            ))
            continue

        sent_count += 1

        try:
            event = EmailEvent(
                account_id=account_id,
                campaign_id=campaign.id,
                contact_id=contact.id,
                primary_recipient=contact.email.strip().lower(),
                event_type="send_to_ses",
                provider="ses",
                message_id=message_id,
                credential_id=body.credential_id,
                sender_domain=sender_domain,
                event_metadata={
                    "tracking_id": tracking_id,
                    "batch_id": batch_id,
                    "email_template_id": template.id,
                },
            )
            db.add(event)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(
                "Campaign %d: failed to record event for contact %d: %s",
                campaign_id, contact.id, exc,
            )

    # ── Mark campaign active if it was in draft ──────────────────────────
    if campaign.status == "draft":
        campaign.status = "active"
        db.commit()

    return CampaignSendResponse(
        campaign_id=campaign.id,
        total_contacts=len(contacts),
        sent=sent_count,
        failed=len(errors),
        errors=errors,
        batch_id=batch_id,
    )
