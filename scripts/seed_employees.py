#!/usr/bin/env python3
"""
Seed demo employee accounts so an admin can add them to an access group.

`add_member` requires the target account to already exist on Kalygo. For a
demo you often want to build the "Employees" roster *before* the employees
have logged in for the first time. This script inserts accounts
(idempotently) for a list of emails so they can be added to a group right away.

Run it INSIDE the ai-api container so it inherits the same POSTGRES_URL / SSL
configuration the app uses:

    docker compose -f docker-compose.dev.yml exec kalygo3-ai-api \
        python scripts/seed_employees.py alice@acme.com bob@acme.com carol@acme.com

With no arguments it seeds a small default demo roster.

Notes:
  - Emails are canonicalized (trimmed + lowercased) to match how accounts are
    stored, so they line up with the group add-member lookup.
  - Seeded accounts have no password/OTP set; they log in normally via the
    OTP flow (request-code finds the existing account and emails a code).
"""
from __future__ import annotations

import sys

from src.db.database import SessionLocal
from src.db.models import Account, UsageCredits

DEFAULT_EMAILS = [
    "ceo@acme.com",
    "alice@acme.com",
    "bob@acme.com",
    "carol@acme.com",
    "dave@acme.com",
]


def _canonical_email(value: str) -> str:
    return value.strip().lower()


def seed(emails: list[str]) -> None:
    canonical = sorted({_canonical_email(e) for e in emails if e.strip()})
    if not canonical:
        print("No emails provided; nothing to do.")
        return

    db = SessionLocal()
    created: list[str] = []
    existing: list[str] = []
    try:
        for email in canonical:
            account = db.query(Account).filter(Account.email == email).first()
            if account:
                existing.append(email)
                continue

            account = Account(email=email)
            db.add(account)
            db.flush()  # assign account.id

            # Mirror signup: a small starting credit so the seeded account
            # behaves like a normally-registered user.
            try:
                db.add(UsageCredits(account_id=account.id, amount=1.00))
            except Exception:
                pass

            created.append(email)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Created {len(created)}: {', '.join(created) or '—'}")
    print(f"Already existed {len(existing)}: {', '.join(existing) or '—'}")


if __name__ == "__main__":
    args = sys.argv[1:]
    seed(args if args else DEFAULT_EMAILS)
