"""
Send Plain-Text Email Tool (AWS SES)

Allows agents to send plain-text emails via Amazon SES using AWS credentials
stored in the caller's credentials database.

Expected credential structure (service_name = AWS_SES):
{
    "aws_access_key_id":     "AKIA...",
    "aws_secret_access_key": "...",
    "aws_region":            "us-east-1",
    "from_email":            "noreply@example.com"
}
"""
from typing import Dict, Any, Optional, TypedDict
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from src.db.models import Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_credential_data
from src.tools.db_read import CredentialError


class EmailSentSuccess(TypedDict):
    """Returned when the email was accepted by SES."""
    message_id: str
    status: str


class EmailSentError(TypedDict):
    """Returned when sending failed."""
    error: str


def _get_ses_credential(credential_id: int, account_id: int, db: Session) -> Dict[str, str]:
    """
    Retrieve and decrypt AWS SES credentials from the credentials database.

    Looks up the credential by ID and verifies it belongs to the given account.
    The decrypted payload must contain at minimum:
        aws_access_key_id, aws_secret_access_key, aws_region, from_email

    Raises:
        CredentialError: if the credential is missing, unauthorised, or malformed.
    """
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.account_id == account_id,
    ).first()

    if not credential:
        raise CredentialError(
            f"Credential with ID {credential_id} not found. "
            "It may have been deleted or you don't have access to it."
        )

    try:
        data = decrypt_credential_data(credential.encrypted_data)
    except Exception as e:
        raise CredentialError(f"Failed to decrypt credential {credential_id}: {e}")

    required_keys = {"aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"}
    missing = required_keys - set(data.keys())
    if missing:
        raise CredentialError(
            f"Credential {credential_id} is missing required keys: {sorted(missing)}. "
            f"Present keys: {sorted(data.keys())}"
        )

    return data


async def create_send_txt_email_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Session,
    auth_token: Optional[str] = None,
    **kwargs,
) -> StructuredTool:
    """
    Create a plain-text email sending tool backed by AWS SES.

    Args:
        tool_config: Tool configuration including:
            - credentialId (int, required): ID of the stored AWS SES credential.
            - name (str, optional): Custom tool name shown to the LLM.
            - description (str, optional): Description shown to the LLM.
        account_id: ID of the authenticated account (used for credential lookup).
        db: SQLAlchemy session (for credential lookup at tool-creation time).
        auth_token: Unused; kept for interface consistency.
        **kwargs: Additional context (unused).

    Returns:
        A LangChain StructuredTool the agent can call with
        ``to_email``, ``subject``, and ``body``.

    Example tool_config:
        {
            "type": "sendTxtEmail",
            "credentialId": 12,
            "name": "send_email",
            "description": "Send a plain-text email to a recipient"
        }
    """
    credential_id = tool_config.get("credentialId")
    if not credential_id:
        raise CredentialError(
            "Missing required field 'credentialId' in sendTxtEmail tool configuration"
        )

    tool_name = (tool_config.get("name") or "send_txt_email").strip()
    description = (
        tool_config.get("description")
        or "Send a plain-text email to a recipient via AWS SES."
    )

    # Resolve and validate the credential at tool-creation time so any
    # misconfiguration is caught before the agent ever runs.
    ses_creds = _get_ses_credential(credential_id, account_id, db)
    print(
        f"[SEND TXT EMAIL TOOL] Tool '{tool_name}' ready "
        f"(from: {ses_creds['from_email']}, region: {ses_creds['aws_region']})"
    )

    async def send_impl(
        to_email: str,
        subject: str,
        body: str,
    ) -> EmailSentSuccess | EmailSentError:
        """Send a plain-text email via AWS SES."""
        print(f"\n{'='*60}")
        print(f"[SEND TXT EMAIL TOOL] TOOL INVOKED: {tool_name}")
        print(f"[SEND TXT EMAIL TOOL] To:      {to_email}")
        print(f"[SEND TXT EMAIL TOOL] Subject: {subject}")
        print(f"{'='*60}\n")

        try:
            import boto3

            client = boto3.client(
                "ses",
                region_name=ses_creds["aws_region"],
                aws_access_key_id=ses_creds["aws_access_key_id"],
                aws_secret_access_key=ses_creds["aws_secret_access_key"],
            )

            response = client.send_email(
                Source=ses_creds["from_email"],
                Destination={"ToAddresses": [to_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )

            message_id = response.get("MessageId", "")
            print(f"[SEND TXT EMAIL TOOL] Email sent successfully. MessageId: {message_id}")
            return {"message_id": message_id, "status": "sent"}

        except Exception as e:
            print(f"[SEND TXT EMAIL TOOL] Failed to send email: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

    class SendEmailInput(BaseModel):
        to_email: str = Field(description="Recipient email address")
        subject: str = Field(description="Subject line of the email")
        body: str = Field(description="Plain-text body of the email")

    return StructuredTool(
        func=send_impl,
        coroutine=send_impl,
        name=tool_name,
        description=description,
        args_schema=SendEmailInput,
    )
