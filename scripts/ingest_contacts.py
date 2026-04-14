"""
Ingest a predefined list of contacts into the `contacts` table.

Existing contacts (matched by e-mail) are skipped; new ones are inserted.

Usage (from the repo root):
    python -m scripts.ingest_contacts
    python -m scripts.ingest_contacts --account-id 2
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.db.database import SessionLocal
from src.db.models import Contact

CONTACTS = [
    {"first_name": "Andres",     "last_name": "Pinate",     "email": "andres@safeharborcp.com"},
    {"first_name": "Andrew",     "last_name": "Klebanow",   "email": "andrewklebanow@safeharborcp.com"},
    {"first_name": "Barbara",    "last_name": "Cepero",     "email": "barbara@safeharborcp.com"},
    {"first_name": "Bernadette", "last_name": "Bodjona",    "email": "bernadette@safeharborcp.com"},
    {"first_name": "Brian",      "last_name": "McCawley",   "email": "brianmccawley@safeharborcp.com"},
    {"first_name": "Carlos A",   "last_name": "Rivera",     "email": "carlos@safeharborcp.com"},
    {"first_name": "Chris",      "last_name": "Spuches",    "email": "cs@safeharborcp.com"},
    {"first_name": "Cyrus",      "last_name": "Borzooyeh",  "email": "cyrus@safeharborcp.com"},
    {"first_name": "David",      "last_name": "Bloch",      "email": "davidbloch@safeharborcp.com"},
    {"first_name": "Emily",      "last_name": "Mayo",       "email": "emilymayo@safeharborcp.com"},
    {"first_name": "Jesus",      "last_name": "Molano",     "email": "jesus@safeharborcp.com"},
    {"first_name": "Mario",      "last_name": "Rosano",     "email": "mario@safeharborcp.com"},
    {"first_name": "Michael",    "last_name": "Moreno",     "email": "michaelmoreno@safeharborcp.com"},
    {"first_name": "Milagros",   "last_name": "Silva",      "email": "milagrossilva@safeharborcp.com"},
    {"first_name": "Nathan",     "last_name": "Kim",        "email": "nathankim@safeharborcp.com"},
    {"first_name": "Rafael",     "last_name": "Serrano",    "email": "rs@safeharborcp.com"},
    {"first_name": "Roxana",     "last_name": "Chiang",     "email": "roxana@safeharborcp.com"},
    {"first_name": "Samantha",   "last_name": "Meland",     "email": "samantha@safeharborcp.com"},
    {"first_name": "Valentina",  "last_name": "Pariente",   "email": "valentinapariente@safeharborcp.com"},
    {"first_name": "Enrique",    "last_name": "Colon",      "email": "mktinfo@safeharborcp.com"},
    {"first_name": "cs@lynxesq.com", "last_name": None,     "email": "cs@lynxesq.com"},
]


def ingest(account_id: int) -> None:
    db = SessionLocal()
    created = skipped = 0
    try:
        for row in CONTACTS:
            email = row["email"].lower()
            existing = db.query(Contact).filter(Contact.email == email).first()
            if existing:
                print(f"⏭  Skipped (already exists): {email}")
                skipped += 1
                continue

            contact = Contact(
                account_id=account_id,
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=email,
                source="import",
            )
            db.add(contact)
            created += 1

        db.commit()
        print(f"\n✅  Done — {created} inserted, {skipped} skipped.")
    except Exception as e:
        db.rollback()
        print(f"❌  Failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Safe Harbor contacts")
    parser.add_argument(
        "--account-id", type=int, default=1,
        help="Account ID to associate the contacts with (default: 1)",
    )
    args = parser.parse_args()
    ingest(args.account_id)
