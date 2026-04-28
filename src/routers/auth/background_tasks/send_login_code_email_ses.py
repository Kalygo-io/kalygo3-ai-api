import logging
import os
import boto3

logger = logging.getLogger(__name__)


def send_login_code_email_ses(to_email: str, code: str) -> None:
    try:
        client = boto3.client(
            "ses",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_KEY"),
        )

        client.send_email(
            Source="noreply@kalygo.io",
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": "Your Kalygo sign-in code"},
                "Body": {
                    "Html": {
                        "Data": (
                            f"<p>Your sign-in code is:</p>"
                            f"<h2 style='letter-spacing:0.2em'>{code}</h2>"
                            f"<p>This code expires in 10 minutes. "
                            f"If you did not request this, you can safely ignore this email.</p>"
                        )
                    },
                    "Text": {
                        "Data": (
                            f"Your Kalygo sign-in code is: {code}\n\n"
                            f"This code expires in 10 minutes.\n"
                            f"If you did not request this, you can safely ignore this email."
                        )
                    },
                },
            },
        )
    except Exception:
        logger.exception("[send_login_code_email_ses] Failed to send login code to %s", to_email)
