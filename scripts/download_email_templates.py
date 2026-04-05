"""
Download all email templates from the database into a local directory tree.

Each template is written to:
    email-templates/<slug>/
        template.html       ← raw HTML with {{variable}} tokens
        manifest.json       ← everything else (id, name, subject, variables …)

Running the script a second time overwrites files so your local copy stays
in sync with whatever is in the DB.

Usage (from kalygo3-ai-api directory):
    python -m scripts.download_email_templates
    python -m scripts.download_email_templates --out-dir ./my-templates
    python -m scripts.download_email_templates --account-id 2
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import EmailTemplate


def slugify(name: str) -> str:
    """Convert a template name to a filesystem-safe directory name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = slug.strip("-")
    return slug or "template"


def download(account_id: int, out_dir: Path) -> None:
    db = SessionLocal()
    try:
        templates = (
            db.query(EmailTemplate)
            .filter(EmailTemplate.account_id == account_id)
            .order_by(EmailTemplate.name)
            .all()
        )
    finally:
        db.close()

    if not templates:
        print(f"ℹ️  No templates found for account_id={account_id}.")
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁  Writing to: {out_dir.resolve()}\n")

    for tmpl in templates:
        slug = slugify(tmpl.name)
        tmpl_dir = out_dir / slug
        tmpl_dir.mkdir(parents=True, exist_ok=True)

        # ── template.html ──────────────────────────────────────────────────────
        html_path = tmpl_dir / "template.html"
        html_path.write_text(tmpl.html_template, encoding="utf-8")

        # ── manifest.json ─────────────────────────────────────────────────────
        manifest = {
            "id": tmpl.id,
            "account_id": tmpl.account_id,
            "name": tmpl.name,
            "slug": slug,
            "description": tmpl.description or "",
            "subject_template": tmpl.subject_template,
            "variables": tmpl.variables or [],
            "created_at": tmpl.created_at.isoformat() if tmpl.created_at else None,
            "updated_at": tmpl.updated_at.isoformat() if tmpl.updated_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        manifest_path = tmpl_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        print(f"  ✅  [{tmpl.id:>4}]  {tmpl.name}  →  email-templates/{slug}/")

    print(f"\n✔  Downloaded {len(templates)} template(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download email templates to local files")
    parser.add_argument(
        "--account-id", type=int, default=1,
        help="Account ID to download templates for (default: 1)",
    )
    parser.add_argument(
        "--out-dir", type=Path,
        default=Path(__file__).parent.parent / "email-templates",
        help="Output directory (default: <repo>/kalygo3-ai-api/email-templates/)",
    )
    args = parser.parse_args()
    download(args.account_id, args.out_dir)
