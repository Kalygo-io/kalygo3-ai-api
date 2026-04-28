"""
Preview a pending HTML email tool approval by sending it to the logged-in user.

Sends the rendered email to the requesting user's own address so they can verify
it looks correct before approving (which sends it to the real recipient).
The approval status is left unchanged — it remains pending.
"""
import logging
import os as _os
import re as _re

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.deps import db_dependency, auth_dependency
from src.db.models import PendingToolApproval, Credential
from src.routers.credentials.encryption import decrypt_credential_data
from .models import ApproveToolApprovalResponse
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

_TRACKING_BASE_URL = _os.getenv("TRACKING_BASE_URL", "http://127.0.0.1:4000")

def _strip_html_tags(html: str) -> str:
    text = _re.sub(r"<(br\s*/?|/?(p|div|tr|li|h[1-6])[^>]*)>", "\n", html, flags=_re.IGNORECASE)
    text = _re.sub(r"<[^>]+>", "", text)
    text = _re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

_PREVIEW_BANNER = """
<div style="background:#f59e0b;color:#000;font-family:sans-serif;font-size:13px;
            font-weight:700;text-align:center;padding:10px 16px;letter-spacing:0.05em;">
  &#128065; PREVIEW — this email has NOT been sent to the recipient
</div>
"""

def _inject_preview_banner(html: str) -> str:
    """Prepend a bright preview banner just after <body> (or at the very top)."""
    match = _re.search(r"(<body[^>]*>)", html, flags=_re.IGNORECASE)
    if match:
        pos = match.end()
        return html[:pos] + _PREVIEW_BANNER + html[pos:]
    return _PREVIEW_BANNER + html

class PreviewOverrides(BaseModel):
    """Optional user-edited values — same shape as ApproveOverrides."""
    subject: str | None = None
    html_body: str | None = None

@router.post("/{approval_id}/preview", response_model=ApproveToolApprovalResponse)
@limiter.limit("30/minute")
async def preview_tool_approval(
    approval_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    overrides: PreviewOverrides | None = None,
):
    """
    Send a preview of a pending HTML email to the currently logged-in user.

    The approval is NOT marked as approved — it stays pending so the user
    can still approve (sending to the real recipient) or reject afterwards.
    """
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
    preview_recipient = auth["email"]
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
            detail=f"Cannot preview a request with status '{approval.status}'",
        )

    if approval.expires_at < now:
        raise HTTPException(status_code=410, detail="This approval request has expired")

    if approval.tool_type != "sendHtmlEmailWithSes":
        raise HTTPException(
            status_code=422,
            detail=f"Preview is only supported for sendHtmlEmailWithSes tools, got '{approval.tool_type}'",
        )

    payload = approval.payload
    credential_id = payload.get("credential_id")

    subject = (
        (overrides.subject.strip() if overrides and overrides.subject and overrides.subject.strip() else None)
        or payload.get("subject", "(no subject)")
    )
    html_body = (
        (overrides.html_body.strip() if overrides and overrides.html_body and overrides.html_body.strip() else None)
        or payload.get("html_body", "")
    )

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

    preview_subject = f"[PREVIEW] {subject}"
    preview_html = _inject_preview_banner(html_body)
    plain_fallback = _strip_html_tags(html_body)

    try:
        import boto3
        client = boto3.client(
            "ses",
            region_name=cred_data["aws_region"],
            aws_access_key_id=cred_data["aws_access_key_id"],
            aws_secret_access_key=cred_data["aws_secret_access_key"],
        )
        client.send_email(
            Source=cred_data["from_email"],
            Destination={"ToAddresses": [preview_recipient]},
            Message={
                "Subject": {"Data": preview_subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": preview_html, "Charset": "UTF-8"},
                    "Text": {"Data": plain_fallback, "Charset": "UTF-8"},
                },
            },
        )
        logger.info("Preview email sent — approval_id=%s to=%s", approval_id, preview_recipient)
    except Exception as e:
        logger.error("Preview send failed — approval_id=%s: %s", approval_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to send preview email: {e}")

    return ApproveToolApprovalResponse(
        id=approval.id,
        status="preview_sent",
        message=f"Preview sent to {preview_recipient}",
    )
