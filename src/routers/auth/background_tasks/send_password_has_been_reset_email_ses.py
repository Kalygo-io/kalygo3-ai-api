import logging
import os
import boto3

logger = logging.getLogger(__name__)


def send_password_has_been_reset_email_ses(to_email: str):
    try:
        client = boto3.client(
            'ses',
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
        )

        client.send_email(
            Source='noreply@kalygo.io',
            Destination={
                'ToAddresses': [to_email]
            },
            Message={
                'Subject': {
                    'Data': 'Password has been reset'
                },
                'Body': {
                    'Html': {
                        'Data': f"<p>Your password has been reset</p>"
                    }
                }
            }
        )
    except Exception:
        logger.exception("[send_password_has_been_reset_email_ses] Failed to send to %s", to_email)
