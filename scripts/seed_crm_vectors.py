"""
Seed the ``crm`` Pinecone namespace with embeddings for all existing
ContactEvent and CareerTimeline rows.

Run this once to backfill vectors for data that was created before the
vector integration was added.  It is idempotent — running it again
simply overwrites existing vectors with the same IDs.

Usage (from the kalygo3-ai-api root):
    python -m scripts.seed_crm_vectors --jwt <YOUR_JWT_TOKEN>
    python -m scripts.seed_crm_vectors --jwt <TOKEN> --account-id 1
    python -m scripts.seed_crm_vectors --jwt <TOKEN> --dry-run
"""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import Contact, ContactEvent, CareerTimeline
from src.services.crm_vector_service import (
    upsert_contact_event_vector,
    upsert_career_timeline_vector,
)


async def seed(token: str, account_id: int | None, dry_run: bool) -> None:
    db = SessionLocal()

    try:
        # ── Gather contact events ─────────────────────────────────────
        event_query = db.query(ContactEvent).join(Contact)
        if account_id is not None:
            event_query = event_query.filter(ContactEvent.account_id == account_id)
        events = event_query.all()

        # ── Gather career timeline entries ────────────────────────────
        career_query = db.query(CareerTimeline).join(Contact)
        if account_id is not None:
            career_query = career_query.filter(CareerTimeline.account_id == account_id)
        career_entries = career_query.all()

        total = len(events) + len(career_entries)
        print(f"\nFound {len(events)} contact events and {len(career_entries)} career timeline entries ({total} total)")

        if total == 0:
            print("Nothing to seed.")
            return

        if dry_run:
            print("[DRY RUN] Would embed and upsert the above. Exiting.")
            return

        # ── Process contact events ────────────────────────────────────
        succeeded = 0
        failed = 0

        for i, event in enumerate(events, 1):
            contact: Contact = event.contact
            label = f"[{i}/{total}] contact_event_{event.id}"
            try:
                await upsert_contact_event_vector(
                    token=token,
                    event_id=event.id,
                    account_id=event.account_id,
                    contact_id=event.contact_id,
                    contact_name=contact.name,
                    contact_email=contact.email,
                    event_type=event.event_type,
                    title=event.title,
                    description=event.description,
                    occurred_at=event.occurred_at,
                )
                print(f"  ✓ {label}  {event.title}")
                succeeded += 1
            except Exception as e:
                print(f"  ✗ {label}  {e}")
                failed += 1

        # ── Process career timeline entries ───────────────────────────
        for j, entry in enumerate(career_entries, len(events) + 1):
            contact: Contact = entry.contact
            label = f"[{j}/{total}] career_timeline_{entry.id}"
            try:
                await upsert_career_timeline_vector(
                    token=token,
                    entry_id=entry.id,
                    account_id=entry.account_id,
                    contact_id=entry.contact_id,
                    contact_name=contact.name,
                    contact_email=contact.email,
                    title=entry.title,
                    description=entry.description,
                    start_date=entry.start_date,
                    end_date=entry.end_date,
                )
                print(f"  ✓ {label}  {entry.title}")
                succeeded += 1
            except Exception as e:
                print(f"  ✗ {label}  {e}")
                failed += 1

        print(f"\n✅  Done — {succeeded} succeeded, {failed} failed out of {total} total.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed the crm Pinecone namespace with embeddings for existing CRM data.",
    )
    parser.add_argument(
        "--jwt", required=True,
        help="A valid JWT token (used to authenticate with the embeddings API).",
    )
    parser.add_argument(
        "--account-id", type=int, default=None,
        help="Only seed data for this account ID. Omit to seed all accounts.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be done without actually embedding or upserting.",
    )
    args = parser.parse_args()

    asyncio.run(seed(token=args.jwt, account_id=args.account_id, dry_run=args.dry_run))
