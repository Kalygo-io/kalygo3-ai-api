"""
Legacy campaign fan-out — now a thin wrapper over the Model A send path.

POST /api/email-campaigns/{campaign_id}/send

Repurposed per the Model A redesign: instead of rendering a stored campaign
template inline, it loops the campaign's linked contact list and calls
``dispatch_one`` per contact — the same idempotent path used by
``POST /api/emails/send``. Templates are never mutated, and re-running is safe
(a confirmed (campaign, contact) send no-ops as ``skipped_duplicate``).

This endpoint carries no per-send ``variables``, so it only resolves contact
personalization + system tokens. Campaigns that need campaign-scoped content
should drive sends through ``POST /api/emails/send`` (e.g. the autoresearch
loop's ``execute_campaign`` helper).

GET /api/email-campaigns/{campaign_id}/unsent — resume helper: the members of a
contact list that do not yet have a confirmed ``send`` for this campaign.
"""
import logging
import uuid as _uuid

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.deps import db_dependency, auth_dependency
from src.db.models import (
    Contact,
    ContactListMember,
    EmailCampaign,
    EmailEvent,
    EmailTemplate,
)
from src.rate_limit import limiter
from src.services.email_dispatch import (
    CredentialError,
    MissingVariablesError,
    SesSendError,
    dispatch_one,
    load_ses_credential,
)

logger = logging.getLogger(__name__)
router = APIRouter()


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
    skipped: int
    failed: int
    errors: list[SendError]
    batch_id: str


class UnsentContact(BaseModel):
    contact_id: int
    email: str


class UnsentResponse(BaseModel):
    campaign_id: int
    contact_list_id: int
    remaining: list[UnsentContact]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_list_contacts(db, account_id: int, contact_list_id: int) -> list[Contact]:
    members = (
        db.query(ContactListMember)
        .filter(
            ContactListMember.contact_list_id == contact_list_id,
            ContactListMember.account_id == account_id,
        )
        .all()
    )
    contact_ids = [m.contact_id for m in members]
    if not contact_ids:
        return []
    return (
        db.query(Contact)
        .filter(Contact.id.in_(contact_ids), Contact.account_id == account_id)
        .all()
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/{campaign_id}/send", response_model=CampaignSendResponse)
@limiter.limit("10/minute")
async def send_campaign(
    campaign_id: int,
    body: CampaignSendRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Send the campaign's linked template to every contact in its linked list.

    Each recipient goes through the shared idempotent ``dispatch_one`` path, so a
    crashed/re-run send only mails the remaining contacts — zero duplicates.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    # Legacy endpoint still derives the template from the campaign link.
    if not campaign.email_template_id:
        raise HTTPException(status_code=422, detail="Campaign has no email template linked")
    if not campaign.contact_list_id:
        raise HTTPException(status_code=422, detail="Campaign has no contact list linked")

    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == campaign.email_template_id,
        EmailTemplate.account_id == account_id,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Linked email template not found")

    contacts = _load_list_contacts(db, account_id, campaign.contact_list_id)
    if not contacts:
        raise HTTPException(status_code=422, detail="Contact list has no members")

    try:
        credential_cfg = load_ses_credential(db, account_id, body.credential_id)
    except CredentialError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)

    batch_id = str(_uuid.uuid4())
    sent = skipped = 0
    errors: list[SendError] = []

    for contact in contacts:
        try:
            result = dispatch_one(
                db,
                account_id=account_id,
                campaign_id=campaign.id,
                template=template,
                contact=contact,
                to_email=contact.email,
                request_vars=None,
                credential_cfg=credential_cfg,
                credential_id=body.credential_id,
                dry_run=body.dry_run,
                batch_id=batch_id,
            )
        except MissingVariablesError as exc:
            tokens = ", ".join(m["token"] for m in exc.missing)
            errors.append(SendError(contact_id=contact.id, email=contact.email,
                                    reason=f"missing required variables: {tokens}"))
            continue
        except SesSendError as exc:
            errors.append(SendError(contact_id=contact.id, email=contact.email, reason=str(exc)))
            continue

        # "validated" (dry_run) is intentionally counted as neither sent nor
        # skipped — a dry run reports only validation errors.
        if result["status"] == "sent":
            sent += 1
        elif result["status"] == "skipped_duplicate":
            skipped += 1

    if not body.dry_run and campaign.status == "draft":
        campaign.status = "active"
        db.commit()

    return CampaignSendResponse(
        campaign_id=campaign.id,
        total_contacts=len(contacts),
        sent=sent,
        skipped=skipped,
        failed=len(errors),
        errors=errors,
        batch_id=batch_id,
    )


@router.get("/{campaign_id}/unsent", response_model=UnsentResponse)
@limiter.limit("60/minute")
async def campaign_unsent(
    campaign_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    contact_list_id: int = Query(
        default=None,
        description="List to compute against; defaults to the campaign's linked list."),
):
    """Members of the list with no confirmed ``send`` for this campaign yet.

    Convenience over ``list members − {contact_id with a send event}`` so clients
    don't compute resume sets by hand.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    list_id = contact_list_id or campaign.contact_list_id
    if not list_id:
        raise HTTPException(
            status_code=422,
            detail="No contact_list_id provided and campaign has none linked")

    contacts = _load_list_contacts(db, account_id, list_id)

    already_sent = {
        row.contact_id
        for row in db.query(EmailEvent.contact_id)
        .filter(
            EmailEvent.account_id == account_id,
            EmailEvent.campaign_id == campaign_id,
            EmailEvent.event_type == "send",
            EmailEvent.contact_id.isnot(None),
        )
        .all()
    }

    remaining = [
        UnsentContact(contact_id=c.id, email=c.email)
        for c in contacts
        if c.id not in already_sent
    ]
    return UnsentResponse(
        campaign_id=campaign_id,
        contact_list_id=list_id,
        remaining=remaining,
    )
