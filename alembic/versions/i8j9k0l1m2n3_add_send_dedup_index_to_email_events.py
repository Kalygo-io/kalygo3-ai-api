"""add (campaign_id, contact_id) send-dedup unique index to email_events

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-06-09

Makes email_events the idempotent ledger for Model A sends. A partial UNIQUE
index on (campaign_id, contact_id) WHERE event_type = 'send' guarantees a given
contact is mailed at most once per campaign, enforced at the DB layer — so a
re-run / crashed-loop restart is safe regardless of client behavior.

The predicate also requires campaign_id and contact_id to be non-null: generic
'send' events (e.g. ad-hoc or webhook-sourced) carry null correlation keys and
must never collide with one another.

NOTE: if pre-existing data already contains duplicate confirmed sends for the
same (campaign_id, contact_id), this index creation will fail; de-duplicate
those rows first.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'i8j9k0l1m2n3'
down_revision: Union[str, None] = 'h7i8j9k0l1m2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_email_events_send_campaign_contact"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "email_events",
        ["campaign_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text(
            "event_type = 'send' AND campaign_id IS NOT NULL AND contact_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="email_events")
