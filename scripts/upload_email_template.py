"""
Push a locally edited template back to the database, or create it if new.

Reads  email-templates/<slug>/template.html   for the HTML
Reads  email-templates/<slug>/manifest.json   for id + metadata

All fields in manifest.json are synced to the DB.  Edit them locally the same
way you would edit the HTML and they will be picked up on the next upload.

If the manifest has no "id" (or id is null), the script creates a new row in
the database and writes the assigned id back into manifest.json so that future
uploads are treated as updates.

Usage (from kalygo3-ai-api directory):

    # Upload one template by its directory slug
    python -m scripts.upload_email_template welcome-email

    # Upload ALL templates in the out-dir
    python -m scripts.upload_email_template --all

    # Override the templates root directory
    python -m scripts.upload_email_template welcome-email --dir ./my-templates

Dry-run (shows what would change, writes nothing):
    python -m scripts.upload_email_template welcome-email --dry-run
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import EmailTemplate

DEFAULT_DIR = Path(__file__).parent.parent / "email-templates"


def _save_manifest(manifest_path: Path, manifest: dict) -> None:
    """Write manifest back to disk (used to persist the DB-assigned id)."""
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _create_template(
    slug: str, manifest: dict, manifest_path: Path, html_body: str, db, dry_run: bool,
) -> bool:
    """Insert a brand-new template row. Returns True on success."""
    account_id = manifest.get("account_id")
    name = manifest.get("name")
    subject_template = manifest.get("subject_template")

    if not account_id:
        print(f"  ❌  {slug}: manifest.json must include 'account_id' to create a new template")
        return False
    if not name:
        print(f"  ❌  {slug}: manifest.json must include 'name' to create a new template")
        return False
    if not subject_template:
        print(f"  ❌  {slug}: manifest.json must include 'subject_template' to create a new template")
        return False

    if dry_run:
        print(f"  🔍  [DRY RUN]  Would CREATE template '{name}' for account {account_id}")
        print(f"       subject_template : {subject_template}")
        print(f"       variables        : {[v.get('name') for v in manifest.get('variables', [])]}")
        print(f"       html length      : {len(html_body)} chars")
        return True

    tmpl = EmailTemplate(
        account_id=account_id,
        name=name,
        description=manifest.get("description"),
        subject_template=subject_template,
        html_template=html_body,
        variables=manifest.get("variables"),
    )
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)

    manifest["id"] = tmpl.id
    manifest["created_at"] = tmpl.created_at.isoformat()
    manifest["updated_at"] = tmpl.updated_at.isoformat()
    _save_manifest(manifest_path, manifest)

    print(f"  ✅  {slug}: created id={tmpl.id} '{tmpl.name}'  (manifest.json updated with new id)")
    return True


def _update_template(
    slug: str, manifest: dict, template_id: int, html_body: str, db, dry_run: bool,
) -> bool:
    """Update an existing template row. Returns True on success."""
    if dry_run:
        print(f"  🔍  [DRY RUN]  Would update template id={template_id} '{manifest.get('name')}'")
        print(f"       subject_template : {manifest.get('subject_template')}")
        print(f"       variables        : {[v.get('name') for v in manifest.get('variables', [])]}")
        print(f"       html length      : {len(html_body)} chars")
        return True

    tmpl = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()

    if not tmpl:
        print(f"  ❌  {slug}: template id={template_id} not found in the database")
        return False

    changes = []
    if manifest.get("name") and tmpl.name != manifest["name"]:
        tmpl.name = manifest["name"]
        changes.append("name")
    if "description" in manifest and tmpl.description != manifest["description"]:
        tmpl.description = manifest["description"] or None
        changes.append("description")
    if manifest.get("subject_template") and tmpl.subject_template != manifest["subject_template"]:
        tmpl.subject_template = manifest["subject_template"]
        changes.append("subject_template")
    if tmpl.html_template != html_body:
        tmpl.html_template = html_body
        changes.append("html_template")
    if "variables" in manifest and tmpl.variables != manifest["variables"]:
        tmpl.variables = manifest["variables"]
        changes.append("variables")

    if not changes:
        print(f"  ✔  {slug}: no changes detected — skipping")
        return True

    db.commit()
    db.refresh(tmpl)
    print(f"  ✅  {slug}: updated id={template_id} '{tmpl.name}'  (changed: {', '.join(changes)})")
    return True


def upload_one(slug: str, templates_dir: Path, dry_run: bool) -> bool:
    """Upload / sync a single template directory. Returns True on success."""
    tmpl_dir = templates_dir / slug

    manifest_path = tmpl_dir / "manifest.json"
    html_path = tmpl_dir / "template.html"

    if not manifest_path.exists():
        print(f"  ❌  {slug}: manifest.json not found at {manifest_path}")
        return False
    if not html_path.exists():
        print(f"  ❌  {slug}: template.html not found at {html_path}")
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"  ❌  {slug}: manifest.json is invalid JSON — {e}")
        return False

    html_body = html_path.read_text(encoding="utf-8")
    template_id = manifest.get("id")
    is_new = not template_id

    db = SessionLocal()
    try:
        if is_new:
            return _create_template(slug, manifest, manifest_path, html_body, db, dry_run)
        else:
            return _update_template(slug, manifest, template_id, html_body, db, dry_run)
    except Exception as e:
        db.rollback()
        print(f"  ❌  {slug}: DB error — {e}")
        return False
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a local email template to the database")
    parser.add_argument(
        "slug", nargs="?",
        help="Slug (directory name) of the template to upload, e.g. 'welcome-email'",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Upload every template found in the templates directory",
    )
    parser.add_argument(
        "--dir", type=Path, default=DEFAULT_DIR,
        help=f"Root templates directory (default: {DEFAULT_DIR})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be changed without writing to the database",
    )
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a template slug or use --all to upload every template.")

    templates_dir: Path = args.dir
    if not templates_dir.exists():
        print(f"❌  Templates directory not found: {templates_dir}")
        print("   Run download_email_templates.py first, or pass --dir to specify the path.")
        sys.exit(1)

    if args.all:
        slugs = sorted(
            d.name for d in templates_dir.iterdir()
            if d.is_dir() and (d / "manifest.json").exists()
        )
        if not slugs:
            print(f"⚠️   No template directories found in {templates_dir}")
            sys.exit(0)
        print(f"📤  Uploading {len(slugs)} template(s) from {templates_dir.resolve()}\n")
    else:
        slugs = [args.slug]
        print(f"📤  Uploading template '{args.slug}' from {templates_dir.resolve()}\n")

    success = sum(upload_one(slug, templates_dir, args.dry_run) for slug in slugs)
    failed = len(slugs) - success
    print(f"\n✔  {success} uploaded" + (f"  |  ❌ {failed} failed" if failed else ""))

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
