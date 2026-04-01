"""
Approve a pending tool action and execute it.

Handles:
  - sendTxtEmail                 — sends via AWS SES
  - sendTxtEmailWithGoogleOAuth  — sends via Google Gmail API (OAuth refresh token)
  - sendTxtEmailWithGoogleSmtp   — sends via Gmail SMTP + App Password
"""
import base64
import email as email_lib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import PendingToolApproval, Credential
from src.routers.credentials.encryption import decrypt_credential_data
from .models import ApproveToolApprovalResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


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

class ApproveOverrides(BaseModel):
    """Optional user-edited values that override what the agent originally composed."""
    to_email: str | None = None
    subject: str | None = None
    body: str | None = None


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
    # Helper: prefer user-edited override over original agent-composed value
    def _resolve(field: str, fallback: str) -> str:
        if overrides:
            v = getattr(overrides, field, None)
            if v is not None and v.strip():
                return v.strip()
        return fallback

    if approval.tool_type == "sendTxtEmail":
        payload = approval.payload
        credential_id = payload.get("credential_id")
        to_email = _resolve("to_email", payload.get("to_email", ""))
        subject = _resolve("subject", payload.get("subject", ""))
        body = _resolve("body", payload.get("body", ""))

        if not credential_id:
            raise HTTPException(status_code=422, detail="Approval payload is missing credential_id")

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()

        if not credential:
            raise HTTPException(status_code=404, detail=f"Credential {credential_id} not found")

        try:
            cred_data = decrypt_credential_data(credential.encrypted_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt credential: {e}")

        required = ["aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"]
        missing = [k for k in required if not cred_data.get(k)]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Credential is missing required AWS SES fields: {missing}",
            )

        try:
            message_id = _send_ses_email(cred_data, to_email, subject, body)
            print(f"[TOOL APPROVAL] ✅ Email sent — approval_id={approval_id} MessageId={message_id}")
        except Exception as e:
            print(f"[TOOL APPROVAL] ❌ SES send failed — approval_id={approval_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")

        approval.status = "approved"
        db.commit()

        return ApproveToolApprovalResponse(
            id=approval.id,
            status="approved",
            message=f"Email sent to {to_email}",
        )

    elif approval.tool_type == "sendTxtEmailWithGoogleOAuth":
        payload = approval.payload
        credential_id = payload.get("credential_id")
        to_email = _resolve("to_email", payload.get("to_email", ""))
        subject = _resolve("subject", payload.get("subject", ""))
        body = _resolve("body", payload.get("body", ""))

        if not credential_id:
            raise HTTPException(status_code=422, detail="Approval payload is missing credential_id")

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()

        if not credential:
            raise HTTPException(status_code=404, detail=f"Credential {credential_id} not found")

        try:
            cred_data = decrypt_credential_data(credential.encrypted_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt credential: {e}")

        required = ["client_id", "client_secret", "refresh_token", "from_email"]
        missing = [k for k in required if not cred_data.get(k)]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Credential is missing required Google OAuth fields: {missing}",
            )

        try:
            message_id = _send_gmail_oauth_email(cred_data, to_email, subject, body)
            print(f"[TOOL APPROVAL] ✅ Gmail OAuth sent — approval_id={approval_id} MessageId={message_id}")
        except Exception as e:
            print(f"[TOOL APPROVAL] ❌ Gmail OAuth send failed — approval_id={approval_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email via Gmail OAuth: {e}")

        approval.status = "approved"
        db.commit()

        return ApproveToolApprovalResponse(
            id=approval.id,
            status="approved",
            message=f"Email sent to {to_email}",
        )

    elif approval.tool_type == "sendTxtEmailWithGoogleSmtp":
        payload = approval.payload
        credential_id = payload.get("credential_id")
        to_email = _resolve("to_email", payload.get("to_email", ""))
        subject = _resolve("subject", payload.get("subject", ""))
        body = _resolve("body", payload.get("body", ""))

        if not credential_id:
            raise HTTPException(status_code=422, detail="Approval payload is missing credential_id")

        credential = db.query(Credential).filter(
            Credential.id == credential_id,
            Credential.account_id == account_id,
        ).first()

        if not credential:
            raise HTTPException(status_code=404, detail=f"Credential {credential_id} not found")

        try:
            cred_data = decrypt_credential_data(credential.encrypted_data)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt credential: {e}")

        required = ["from_email", "app_password"]
        missing = [k for k in required if not cred_data.get(k)]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Credential is missing required Gmail SMTP fields: {missing}",
            )

        try:
            _send_gmail_smtp_email(cred_data, to_email, subject, body)
            print(f"[TOOL APPROVAL] ✅ Gmail SMTP sent — approval_id={approval_id}")
        except Exception as e:
            print(f"[TOOL APPROVAL] ❌ Gmail SMTP send failed — approval_id={approval_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email via Gmail SMTP: {e}")

        approval.status = "approved"
        db.commit()

        return ApproveToolApprovalResponse(
            id=approval.id,
            status="approved",
            message=f"Email sent to {to_email}",
        )

    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported tool type for approval execution: '{approval.tool_type}'",
        )
