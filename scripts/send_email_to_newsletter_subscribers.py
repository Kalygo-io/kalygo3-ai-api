"""
Script to send newsletter emails to subscribed users.

This script reads the newsletter content from a text file and sends it to all
accounts with newsletter_subscribed=True using AWS SES.

Usage:
    # Dry run (shows who would receive emails without sending)
    python scripts/send_email_to_newsletter_subscribers.py --dry-run

    # Send emails with default subject
    python scripts/send_email_to_newsletter_subscribers.py

    # Send emails with custom subject
    python scripts/send_email_to_newsletter_subscribers.py --subject "January 2026 Newsletter"

    # Use a different content file
    python scripts/send_email_to_newsletter_subscribers.py --content-file scripts/special_update.txt

Environment Variables Required:
    - POSTGRES_URL: Database connection string
    - AWS_REGION: AWS region for SES
    - AWS_ACCESS_KEY_ID: AWS access key
    - AWS_SECRET_KEY: AWS secret key

Optional Environment Variables:
    - NEWSLETTER_FROM_EMAIL: Sender email (default: noreply@kalygo.io)
    - NEWSLETTER_RATE_LIMIT: Emails per second (default: 10, SES limit is 14/sec)
"""
import os
import sys
import time
import argparse
from datetime import datetime
from typing import List, Tuple

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Load environment variables from .env file at project root
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

import boto3
from botocore.exceptions import ClientError

from src.db.database import SessionLocal
from src.db.models import Account


# Constants
DEFAULT_FROM_EMAIL = "noreply@kalygo.io"
DEFAULT_RATE_LIMIT = 10  # emails per second (SES default limit is 14/sec)
DEFAULT_CONTENT_FILE = os.path.join(os.path.dirname(__file__), "update.txt")
DEFAULT_SUBJECT = "Newsletter Update"


def validate_environment() -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are set.
    
    Returns:
        Tuple of (is_valid, list_of_missing_vars)
    """
    required_vars = [
        "POSTGRES_URL",
        "AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_KEY",
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    return len(missing) == 0, missing


def get_ses_client():
    """Create and return an AWS SES client."""
    return boto3.client(
        'ses',
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
    )


def get_newsletter_subscribers(db) -> List[Account]:
    """
    Query the database for all accounts subscribed to the newsletter.
    
    Args:
        db: Database session
        
    Returns:
        List of Account objects with newsletter_subscribed=True
    """
    return db.query(Account).filter(Account.newsletter_subscribed == True).all()


def read_content_file(file_path: str) -> str:
    """
    Read the newsletter content from a text file.
    
    Args:
        file_path: Path to the content file
        
    Returns:
        Content string
        
    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Content file not found: {file_path}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def text_to_html(text: str) -> str:
    """
    Convert plain text to simple HTML with preserved formatting.
    
    Args:
        text: Plain text content
        
    Returns:
        HTML formatted content
    """
    # Escape HTML special characters
    html = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Convert newlines to <br> tags
    html = html.replace('\n', '<br>\n')
    
    # Wrap in a basic HTML structure
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
    </style>
</head>
<body>
{html}
<br><br>
<hr>
<p style="font-size: 12px; color: #666;">
    You received this email because you subscribed to our newsletter.
    <br>
    To unsubscribe, update your preferences in your account settings.
</p>
</body>
</html>
"""


def send_email(client, from_email: str, to_email: str, subject: str, html_body: str, text_body: str) -> Tuple[bool, str]:
    """
    Send an email using AWS SES.
    
    Args:
        client: SES client
        from_email: Sender email address
        to_email: Recipient email address
        subject: Email subject
        html_body: HTML content
        text_body: Plain text content (fallback)
        
    Returns:
        Tuple of (success, message_id_or_error)
    """
    try:
        response = client.send_email(
            Source=from_email,
            Destination={
                'ToAddresses': [to_email]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': text_body,
                        'Charset': 'UTF-8'
                    },
                    'Html': {
                        'Data': html_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        return True, response['MessageId']
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        return False, f"{error_code}: {error_message}"
    except Exception as e:
        return False, str(e)


def send_newsletter(
    content_file: str,
    subject: str,
    dry_run: bool = False,
    rate_limit: int = DEFAULT_RATE_LIMIT
) -> Tuple[int, int, List[str]]:
    """
    Send newsletter to all subscribed users.
    
    Args:
        content_file: Path to the newsletter content file
        subject: Email subject line
        dry_run: If True, don't actually send emails
        rate_limit: Max emails per second
        
    Returns:
        Tuple of (success_count, error_count, list_of_errors)
    """
    db = SessionLocal()
    errors = []
    success_count = 0
    error_count = 0
    
    try:
        # Read newsletter content
        print(f"Reading content from: {content_file}")
        text_content = read_content_file(content_file)
        html_content = text_to_html(text_content)
        
        print(f"Content length: {len(text_content)} characters")
        print()
        
        # Get subscribers
        subscribers = get_newsletter_subscribers(db)
        total_subscribers = len(subscribers)
        
        if total_subscribers == 0:
            print("No subscribers found with newsletter_subscribed=True")
            return 0, 0, []
        
        print(f"Found {total_subscribers} subscriber(s)")
        print()
        
        if dry_run:
            print("[DRY RUN] Would send to the following addresses:")
            for account in subscribers:
                print(f"  - {account.email} (ID: {account.id})")
            print()
            print(f"[DRY RUN] Subject: {subject}")
            print()
            print("[DRY RUN] Preview of HTML content (first 500 chars):")
            print("-" * 40)
            print(html_content[:500])
            print("-" * 40)
            return total_subscribers, 0, []
        
        # Initialize SES client
        from_email = os.getenv("NEWSLETTER_FROM_EMAIL", DEFAULT_FROM_EMAIL)
        client = get_ses_client()
        
        print(f"Sending from: {from_email}")
        print(f"Subject: {subject}")
        print(f"Rate limit: {rate_limit} emails/second")
        print()
        
        # Calculate delay between emails
        delay = 1.0 / rate_limit if rate_limit > 0 else 0
        
        # Send emails
        for i, account in enumerate(subscribers, 1):
            email = account.email
            
            print(f"[{i}/{total_subscribers}] Sending to {email}...", end=" ")
            
            success, result = send_email(
                client=client,
                from_email=from_email,
                to_email=email,
                subject=subject,
                html_body=html_content,
                text_body=text_content
            )
            
            if success:
                print(f"✓ (MessageId: {result[:20]}...)")
                success_count += 1
            else:
                print(f"✗ ({result})")
                error_count += 1
                errors.append(f"{email}: {result}")
            
            # Rate limiting - sleep between emails (except after the last one)
            if i < total_subscribers and delay > 0:
                time.sleep(delay)
        
        return success_count, error_count, errors
        
    except FileNotFoundError as e:
        print(f"✗ ERROR: {e}")
        return 0, 1, [str(e)]
    except Exception as e:
        print(f"✗ Fatal error: {str(e)}")
        return success_count, error_count + 1, errors + [str(e)]
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Send newsletter emails to subscribed users",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Preview who would receive emails (recommended first step)
    python scripts/send_email_to_newsletter_subscribers.py --dry-run

    # Send with custom subject
    python scripts/send_email_to_newsletter_subscribers.py --subject "January 2026 Newsletter"

    # Use a different content file
    python scripts/send_email_to_newsletter_subscribers.py --content-file scripts/promo.txt
        """
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show who would receive emails without actually sending"
    )
    
    parser.add_argument(
        "--subject",
        type=str,
        default=DEFAULT_SUBJECT,
        help=f"Email subject line (default: '{DEFAULT_SUBJECT}')"
    )
    
    parser.add_argument(
        "--content-file",
        type=str,
        default=DEFAULT_CONTENT_FILE,
        help=f"Path to newsletter content file (default: scripts/update.txt)"
    )
    
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=DEFAULT_RATE_LIMIT,
        help=f"Max emails per second (default: {DEFAULT_RATE_LIMIT})"
    )
    
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    # Print header
    print("=" * 60)
    print("Newsletter Email Sender")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    # Validate environment
    is_valid, missing_vars = validate_environment()
    if not is_valid:
        print("✗ ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print()
        print("Please set these variables in your .env file or environment.")
        sys.exit(1)
    
    print("✓ Environment variables validated")
    
    # Check content file exists
    if not os.path.exists(args.content_file):
        print(f"✗ ERROR: Content file not found: {args.content_file}")
        print()
        print("Create a content file or specify a different path with --content-file")
        sys.exit(1)
    
    print(f"✓ Content file found: {args.content_file}")
    print()
    
    # Confirmation for non-dry-run
    if not args.dry_run and not args.yes:
        print("⚠ WARNING: This will send real emails to all newsletter subscribers!")
        print()
        print("Run with --dry-run first to preview recipients.")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            sys.exit(0)
        print()
    
    # Run the newsletter send
    success, errors, error_list = send_newsletter(
        content_file=args.content_file,
        subject=args.subject,
        dry_run=args.dry_run,
        rate_limit=args.rate_limit
    )
    
    # Print summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    if args.dry_run:
        print(f"[DRY RUN] Would have sent to {success} recipient(s)")
    else:
        print(f"Successfully sent: {success}")
        print(f"Failed: {errors}")
        
        if error_list:
            print()
            print("Errors:")
            for error in error_list:
                print(f"  - {error}")
    
    print()
    print("Done!")
    
    # Exit with error code if there were failures
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
