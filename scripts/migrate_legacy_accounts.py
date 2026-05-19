"""
Migrate the legacy Kalygo user list (emails + newsletter signups) into the
new `accounts` table.

Source: a `pg_dump` of the old platform schema (default:
`scratchspace/kalygo_9_21_2024.sql`). Two tables are read from the dump's
COPY blocks:

  * "Account"     -> every email that ever signed on to the old platform
  * "MailingList" -> emails that opted in to the newsletter

Migration rules (decided with the product owner):

  * Names are NOT migrated. The new `accounts` table has no name column and
    only a handful of legacy rows had a name anyway.
  * Every legacy account email is inserted. `newsletter_subscribed` is True
    iff that email also appears in the legacy MailingList.
  * Newsletter-only emails (in MailingList but never an account) are ALSO
    inserted as accounts with `newsletter_subscribed=True`, so the new DB
    holds the complete list of everyone who signed on OR subscribed.
  * Emails are lowercased (matches scripts/ingest_contacts.py).
  * Idempotent: an email already present in `accounts` is skipped, so the
    script is safe to re-run.

Optionally (--contacts-account-id N) the same email set is also inserted
into the `contacts` table, owned by account N:

  * No names are fabricated. `contacts.first_name` is NOT NULL, so the email
    is used as first_name (the scripts/ingest_contacts.py convention);
    last_name / middle_name are left NULL.
  * `contacts.email` is globally unique, so emails that already exist as a
    contact (under any account) are skipped. Safe to re-run.

Usage (from the repo root):
    python -m scripts.migrate_legacy_accounts --dry-run
    python -m scripts.migrate_legacy_accounts
    python -m scripts.migrate_legacy_accounts --sql-file path/to/dump.sql
    python -m scripts.migrate_legacy_accounts --contacts-account-id 1 --dry-run
    python -m scripts.migrate_legacy_accounts --contacts-account-id 1
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import Account, Contact

DEFAULT_SQL_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scratchspace",
    "kalygo_9_21_2024.sql",
)


def parse_copy_block(lines: list[str], table: str) -> list[dict[str, str | None]]:
    """
    Extract the rows of a single `COPY public."<table>" (...) FROM stdin;`
    block from a pg_dump file as a list of {column: value} dicts.

    Postgres text-format COPY uses a literal `\\N` for NULL and is tab
    delimited; the block is terminated by a line containing only `\\.`.
    """
    header_prefix = f'COPY public."{table}" ('
    for i, line in enumerate(lines):
        if line.startswith(header_prefix):
            col_str = line[len(header_prefix):line.index(")", len(header_prefix))]
            columns = [c.strip().strip('"') for c in col_str.split(",")]
            rows: list[dict[str, str | None]] = []
            for data_line in lines[i + 1:]:
                if data_line == "\\.":
                    return rows
                values = [
                    None if v == "\\N" else v
                    for v in data_line.split("\t")
                ]
                rows.append(dict(zip(columns, values)))
            raise ValueError(f'COPY block for "{table}" was not terminated by \\.')
    raise ValueError(f'No COPY block found for table "{table}" in dump')


def build_migration_set(sql_file: str) -> dict[str, bool]:
    """
    Return {email_lowercased: newsletter_subscribed} for every legacy
    account email plus every newsletter-only email.
    """
    with open(sql_file, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    account_rows = parse_copy_block(lines, "Account")
    mailing_rows = parse_copy_block(lines, "MailingList")

    newsletter_emails = {
        r["email"].strip().lower()
        for r in mailing_rows
        if r.get("email")
    }

    result: dict[str, bool] = {}
    for r in account_rows:
        # One legacy row (id=269) is a half-finished signup with a blank
        # email; an account with no email can't be migrated, so skip it.
        if not r.get("email"):
            continue
        email = r["email"].strip().lower()
        result[email] = email in newsletter_emails

    # Newsletter-only signups (never created an account) are added too.
    for email in newsletter_emails:
        result.setdefault(email, True)

    return result


def migrate(sql_file: str, dry_run: bool) -> None:
    migration = build_migration_set(sql_file)
    subscribed = sum(1 for v in migration.values() if v)
    print(
        f"Parsed dump: {len(migration)} unique emails "
        f"({subscribed} newsletter-subscribed, "
        f"{len(migration) - subscribed} not subscribed)"
    )

    db = SessionLocal()
    created = skipped = 0
    try:
        existing = {
            e.lower()
            for (e,) in db.query(Account.email).all()
            if e
        }
        for email in sorted(migration):
            if email in existing:
                skipped += 1
                continue
            created += 1
            if dry_run:
                continue
            db.add(Account(email=email, newsletter_subscribed=migration[email]))

        if dry_run:
            db.rollback()
            print(
                f"\n[DRY RUN] Would insert {created}, would skip "
                f"{skipped} (already in accounts). No changes written."
            )
            return

        db.commit()
        print(f"\nDone - {created} inserted, {skipped} skipped (already existed).")
    except Exception as e:
        db.rollback()
        print(f"Failed: {e}")
        raise
    finally:
        db.close()


def migrate_contacts(account_id: int, sql_file: str, dry_run: bool) -> None:
    """
    Insert the same legacy email set into `contacts`, owned by account_id.

    No names are fabricated: the email is used as first_name (NOT NULL),
    last_name / middle_name stay NULL. Emails already present as a contact
    (the column is globally unique) are skipped, so this is re-runnable.
    """
    emails = sorted(build_migration_set(sql_file))
    print(f"Parsed dump: {len(emails)} unique emails -> contacts for account {account_id}")

    db = SessionLocal()
    created = skipped = 0
    try:
        if db.query(Account.id).filter(Account.id == account_id).first() is None:
            raise ValueError(f"account_id {account_id} does not exist")

        existing = {
            e.lower()
            for (e,) in db.query(Contact.email).all()
            if e
        }
        for email in emails:
            if email in existing:
                skipped += 1
                continue
            created += 1
            if dry_run:
                continue
            db.add(Contact(
                account_id=account_id,
                first_name=email,
                email=email,
                source="import",
            ))

        if dry_run:
            db.rollback()
            print(
                f"\n[DRY RUN] Would insert {created} contacts, would skip "
                f"{skipped} (already a contact). No changes written."
            )
            return

        db.commit()
        print(f"\nDone - {created} contacts inserted, {skipped} skipped (already existed).")
    except Exception as e:
        db.rollback()
        print(f"Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate legacy Kalygo emails + newsletter signups into accounts"
    )
    parser.add_argument(
        "--sql-file", default=DEFAULT_SQL_FILE,
        help=f"Path to the legacy pg_dump (default: {DEFAULT_SQL_FILE})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and report counts without writing to the database",
    )
    parser.add_argument(
        "--contacts-account-id", type=int, default=None,
        help="If set, migrate the email set into `contacts` owned by this "
             "account instead of into `accounts`",
    )
    args = parser.parse_args()
    if args.contacts_account_id is not None:
        migrate_contacts(args.contacts_account_id, args.sql_file, args.dry_run)
    else:
        migrate(args.sql_file, args.dry_run)
