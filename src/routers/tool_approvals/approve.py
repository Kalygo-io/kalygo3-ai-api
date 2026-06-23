"""
Approve a pending tool action and execute it.

Handles:
  - sendTxtEmailWithSes          — sends plain-text email via AWS SES
  - sendHtmlEmailWithSes         — sends agent-authored HTML email via AWS SES
  - sendTxtEmailWithGoogleOAuth  — sends via Google Gmail API (OAuth refresh token)
  - sendTxtEmailWithGoogleSmtp   — sends via Gmail SMTP + App Password
"""
import base64
import email as email_lib
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import PendingToolApproval, Credential, EmailEvent, EmailTemplate
from src.routers.credentials.encryption import decrypt_credential_data
from .models import ApproveToolApprovalResponse
from .email_html import inject_tracking_pixel, strip_html_tags

logger = logging.getLogger(__name__)

router = APIRouter()

import re as _re
import uuid as _uuid

def _record_send_event(
    db,
    *,
    account_id: int,
    tool_approval_id: int,
    to_email: str,
    provider: str,
    message_id: str,
    credential_id: int | None = None,
    sender_domain: str | None = None,
    extra_metadata: dict | None = None,
) -> None:
    """Write an email_events row with event_type='send_to_ses' after handing off to the provider."""
    try:
        event = EmailEvent(
            account_id=account_id,
            tool_approval_id=tool_approval_id,
            primary_recipient=to_email.strip().lower(),
            event_type="send_to_ses",
            provider=provider,
            message_id=message_id,
            credential_id=credential_id,
            sender_domain=sender_domain,
            event_metadata=extra_metadata or None,
        )
        db.add(event)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Failed to record send event: %s", exc)

def _send_ses_email(ses_cfg: dict, to_email: str, subject: str, body: str) -> str:
    """Send plain-text email via boto3/SES. Returns the SES MessageId."""
    import boto3

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
            "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
        },
    )
    return response.get("MessageId", "unknown")

def _send_ses_html_email(ses_cfg: dict, to_email: str, subject: str, html_body: str) -> str:
    """Send an agent-authored HTML email via boto3/SES.
    html_body is delivered verbatim as the HTML part; a stripped plain-text
    fallback is generated automatically for non-HTML mail clients.
    Returns the SES MessageId."""
    import boto3

    plain_fallback = strip_html_tags(html_body)
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

def _send_gmail_oauth_email(google_cfg: dict, to_email: str, subject: str, body: str) -> str:
    """
    Send plain-text email via the Gmail REST API using an OAuth refresh token.

    Exchanges the refresh token for a fresh access token, then calls
    gmail.users.messages.send.  Returns the Gmail message ID.

    Required google_cfg keys: client_id, client_secret, refresh_token, from_email.
    """
    import httpx

    token_resp = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": google_cfg["client_id"],
            "client_secret": google_cfg["client_secret"],
            "refresh_token": google_cfg["refresh_token"],
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    if token_resp.status_code != 200:
        raise RuntimeError(
            f"Failed to refresh Google access token: {token_resp.status_code} {token_resp.text}"
        )
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise RuntimeError("Google token response did not contain an access_token")

    msg = email_lib.message.EmailMessage()
    msg["From"] = google_cfg["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    send_resp = httpx.post(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"raw": raw},
        timeout=15,
    )
    if send_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"Gmail API send failed: {send_resp.status_code} {send_resp.text}"
        )
    return send_resp.json().get("id", "unknown")

def _send_gmail_smtp_email(smtp_cfg: dict, to_email: str, subject: str, body: str) -> None:
    """
    Send plain-text email via Gmail SMTP using an App Password.

    Required smtp_cfg keys: from_email, app_password.
    """
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_cfg["from_email"]
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(smtp_cfg["from_email"], smtp_cfg["app_password"])
        server.sendmail(smtp_cfg["from_email"], to_email, msg.as_string())

from pydantic import BaseModel
from src.rate_limit import limiter

class ApproveOverrides(BaseModel):
    """Optional user-edited values that override what the agent originally composed."""
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None       # plain-text email body (sendTxtEmail* tools)
    html_body: str | None = None  # HTML email body (sendHtmlEmailWithSes)

@router.post("/{approval_id}/approve", response_model=ApproveToolApprovalResponse)
@limiter.limit("60/minute")
async def approve_tool_approval(
    approval_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    overrides: ApproveOverrides | None = None,
):
    """
    Approve and immediately execute a pending tool action.

    An optional JSON body may supply overrides for to_email / subject / body,
    allowing the user to edit the agent-composed email before sending.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
    now = datetime.now(timezone.utc)

    approval = db.query(PendingToolApproval).filter(
        PendingToolApproval.id == approval_id,
        PendingToolApproval.account_id == account_id,
    ).first()

    if not approval:
        raise HTTPException(status_code=404, detail="Tool approval request not found")

    if approval.status != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve a request with status '{approval.status}'",
        )

    if approval.expires_at < now:
        approval.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="This approval request has expired")

    # ── Execute the tool ────────────────────────────────────────────────────
    def _resolve(field: str, fallback: str) -> str:
        """Prefer user-edited override over original agent-composed value."""
        if overrides:
            v = getattr(overrides, field, None)
            if v is not None and v.strip():
                return v.strip()
        return fallback

    # Provider configs: required credential fields, send function, and provider tag
    _PROVIDER_MAP = {
        "sendTxtEmailWithSes": {
            "required": ["aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"],
            "provider": "ses",
            "send": lambda cred, to, subj, body: _send_ses_email(cred, to, subj, body),
            "label": "AWS SES",
        },
        "sendHtmlEmailWithSes": {
            "required": ["aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"],
            "provider": "ses",
            "send": lambda cred, to, subj, body: _send_ses_html_email(cred, to, subj, body),
            "label": "AWS SES",
        },
        "sendTxtEmailWithGoogleOAuth": {
            "required": ["client_id", "client_secret", "refresh_token", "from_email"],
            "provider": "google_oauth",
            "send": lambda cred, to, subj, body: _send_gmail_oauth_email(cred, to, subj, body),
            "label": "Google OAuth",
        },
        "sendTxtEmailWithGoogleSmtp": {
            "required": ["from_email", "app_password"],
            "provider": "google_smtp",
            "send": lambda cred, to, subj, body: (_send_gmail_smtp_email(cred, to, subj, body), "smtp")[1],
            "label": "Gmail SMTP",
        },
    }

    provider_cfg = _PROVIDER_MAP.get(approval.tool_type)
    if not provider_cfg:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported tool type for approval execution: '{approval.tool_type}'",
        )

    payload = approval.payload
    credential_id = payload.get("credential_id")
    to_email = _resolve("to_email", payload.get("to_email", ""))
    subject = _resolve("subject", payload.get("subject", ""))

    # Resolve body: HTML emails use html_body, others use plain body
    if approval.tool_type == "sendHtmlEmailWithSes":
        body = (
            (overrides.html_body.strip() if overrides and overrides.html_body and overrides.html_body.strip() else None)
            or payload.get("html_body", "")
        )
    else:
        body = _resolve("body", payload.get("body", ""))

    if not credential_id:
        raise HTTPException(status_code=422, detail="Approval payload is missing credential_id")

    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.account_id == account_id,
    ).first()

    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")

    try:
        cred_data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        logger.error("Failed to decrypt credential for approval %s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail="Failed to decrypt credential")

    missing = [k for k in provider_cfg["required"] if not cred_data.get(k)]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Credential is missing required {provider_cfg['label']} fields.",
        )

    from_email = cred_data["from_email"]

    tracking_id = None
    if approval.tool_type == "sendHtmlEmailWithSes":
        # Reuse a tracking_id already embedded in the HTML (e.g. from star-rating
        # links at /t/r/{uuid}/), so the open pixel and rating clicks share the
        # same identifier stored in event_metadata.
        existing = _re.search(r"/t/r/([0-9a-f\-]{36})/", body)
        tracking_id = existing.group(1) if existing else str(_uuid.uuid4())
        body = inject_tracking_pixel(body, tracking_id)

    try:
        message_id = provider_cfg["send"](cred_data, to_email, subject, body)
        logger.info("%s email sent — approval_id=%s MessageId=%s", provider_cfg["label"], approval_id, message_id)
    except Exception as e:
        logger.error("%s send failed — approval_id=%s: %s", provider_cfg["label"], approval_id, e)
        raise HTTPException(status_code=500, detail="Failed to send email. Please try again.")

    approval.status = "approved"
    db.commit()

    extra_metadata = {"tracking_id": tracking_id} if tracking_id else None

    _record_send_event(
        db,
        account_id=account_id,
        tool_approval_id=approval_id,
        to_email=to_email,
        provider=provider_cfg["provider"],
        message_id=message_id,
        credential_id=credential_id,
        sender_domain=from_email.split("@")[1] if "@" in from_email else None,
        extra_metadata=extra_metadata,
    )

    return ApproveToolApprovalResponse(
        id=approval.id,
        status="approved",
        message=f"Email sent to {to_email}",
    )
