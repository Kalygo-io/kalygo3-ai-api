"""
Import SES email templates into Kalygo's email_templates table.

For each template name provided (or all templates listed in SES), this script:
  1. Calls ses.get_template() via boto3 to fetch TemplateName, SubjectPart, HtmlPart
  2. Inserts (or skips if already present) an EmailTemplate row for the given account

Usage (from the kalygo3-ai-api directory):

    # Import a specific set of templates
    python -m scripts.import_ses_templates \
        --template-names BRANDED_JOB_COMPLETE BRANDED_HEADER_AND_MAIN_AND_FOOTER \
        --account-id 1

    # Import ALL templates currently in SES
    python -m scripts.import_ses_templates --all --account-id 1

    # Dry-run (print what would be imported without writing to DB)
    python -m scripts.import_ses_templates --all --account-id 1 --dry-run

AWS credentials are read from the environment (AWS_ACCESS_KEY_ID /
AWS_SECRET_ACCESS_KEY / AWS_DEFAULT_REGION) or from ~/.aws/credentials,
exactly as the rest of the application expects them.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.exceptions import ClientError

from src.db.database import SessionLocal
from src.db.models import EmailTemplate


def list_all_ses_template_names(ses_client) -> list[str]:
    """Return every template name registered in SES (handles pagination)."""
    names = []
    paginator = ses_client.get_paginator("list_templates")
    for page in paginator.paginate():
        for meta in page.get("TemplatesMetadata", []):
            names.append(meta["Name"])
    return names


def fetch_ses_template(ses_client, template_name: str) -> dict | None:
    """
    Fetch a single SES template.
    Returns a dict with keys: name, subject, html
    Returns None if the template doesn't exist.
    """
    try:
        resp = ses_client.get_template(TemplateName=template_name)
        tpl = resp["Template"]
        return {
            "name": tpl["TemplateName"],
            "subject": tpl.get("SubjectPart", ""),
            "html": tpl.get("HtmlPart", ""),
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "TemplateDoesNotExist":
            print(f"  ⚠️  Template '{template_name}' not found in SES — skipping.")
            return None
        raise


def import_template(db, account_id: int, tpl: dict, dry_run: bool) -> None:
    """Insert the template into the DB, skipping if it already exists."""
    existing = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.account_id == account_id,
            EmailTemplate.name == tpl["name"],
        )
        .first()
    )

    if existing:
        print(f"  ℹ️  '{tpl['name']}' already exists for account {account_id} (id={existing.id}) — skipping.")
        return

    if dry_run:
        print(f"  [dry-run] Would import '{tpl['name']}' (subject: {tpl['subject'][:60]!r})")
        return

    row = EmailTemplate(
        account_id=account_id,
        name=tpl["name"],
        description="Imported from Amazon SES",
        subject_template=tpl["subject"],
        html_template=tpl["html"],
        variables=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    print(f"  ✅  Imported '{row.name}' — id={row.id}, account_id={account_id}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import SES email templates into Kalygo"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--template-names",
        nargs="+",
        metavar="NAME",
        help="One or more SES template names to import",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Import every template currently in SES",
    )
    parser.add_argument(
        "--account-id",
        type=int,
        default=1,
        help="Kalygo account ID to attach templates to (default: 1)",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        help="AWS region (default: AWS_DEFAULT_REGION env var or us-east-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be imported without writing to the database",
    )
    args = parser.parse_args()

    ses = boto3.client("ses", region_name=args.region)

    if args.all:
        print(f"Fetching template list from SES ({args.region})…")
        template_names = list_all_ses_template_names(ses)
        if not template_names:
            print("No templates found in SES.")
            sys.exit(0)
        print(f"Found {len(template_names)} template(s): {', '.join(template_names)}\n")
    else:
        template_names = args.template_names

    db = SessionLocal()
    try:
        for name in template_names:
            print(f"Processing '{name}'…")
            tpl = fetch_ses_template(ses, name)
            if tpl is None:
                continue
            import_template(db, args.account_id, tpl, dry_run=args.dry_run)
    except Exception as e:
        db.rollback()
        print(f"\n❌  Unexpected error: {e}")
        raise
    finally:
        db.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
