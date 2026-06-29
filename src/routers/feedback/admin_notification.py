import html
import logging
import os

import boto3

logger = logging.getLogger(__name__)

# Hardcoded admin recipient for now. Every feedback submission is emailed here.
ADMIN_EMAIL = "tad@cmdlabs.io"

# Human-readable labels for the form's category slugs.
CATEGORY_LABELS = {
    "bug": "Something's broken",
    "feature": "Feature request",
    "question": "Question / help",
    "other": "Other",
}


def send_feedback_notification_to_admin(
    *,
    client: str,
    category: str,
    email: str | None,
    message: str,
) -> None:
    """Email the admin that new feedback arrived. Best-effort; never raises.

    Designed to run as a FastAPI BackgroundTask so the request returns fast.
    """
    try:
        category_label = CATEGORY_LABELS.get(category, category)
        from_address = email or "(not provided)"

        subject = f"[{client}] New feedback: {category_label}"

        safe_message = html.escape(message).replace("\n", "<br>")
        html_body = (
            f"<h2>New feedback from {html.escape(client)}</h2>"
            f"<p><strong>Category:</strong> {html.escape(category_label)}</p>"
            f"<p><strong>Reply-to:</strong> {html.escape(from_address)}</p>"
            f"<hr>"
            f"<p>{safe_message}</p>"
        )
        text_body = (
            f"New feedback from {client}\n\n"
            f"Category: {category_label}\n"
            f"Reply-to: {from_address}\n\n"
            f"{message}"
        )

        ses_client = boto3.client(
            "ses",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
        )

        send_kwargs = {
            "Source": "noreply@kalygo.io",
            "Destination": {"ToAddresses": [ADMIN_EMAIL]},
            "Message": {
                "Subject": {"Data": subject},
                "Body": {
                    "Html": {"Data": html_body},
                    "Text": {"Data": text_body},
                },
            },
        }
        # When the submitter left an email, make replies go straight to them.
        if email:
            send_kwargs["ReplyToAddresses"] = [email]

        ses_client.send_email(**send_kwargs)
    except Exception:
        logger.exception(
            "[send_feedback_notification_to_admin] Failed to notify admin of feedback from %s",
            client,
        )
