"""
Approve a pending tool action and execute it.

Currently handles: sendTxtEmail — decrypts the stored credential at execution
time (the payload stores only the credential_id, never plaintext secrets) and
sends the email via AWS SES.
"""
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


@router.post("/{approval_id}/approve", response_model=ApproveToolApprovalResponse)
@limiter.limit("60/minute")
async def approve_tool_approval(
    approval_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """
    Approve and immediately execute a pending tool action.

    For sendTxtEmail: decrypts the stored AWS SES credential and sends the
    email on behalf of the account.
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
    if approval.tool_type == "sendTxtEmail":
        payload = approval.payload
        credential_id = payload.get("credential_id")
        to_email = payload.get("to_email", "")
        subject = payload.get("subject", "")
        body = payload.get("body", "")

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

    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported tool type for approval execution: '{approval.tool_type}'",
        )
