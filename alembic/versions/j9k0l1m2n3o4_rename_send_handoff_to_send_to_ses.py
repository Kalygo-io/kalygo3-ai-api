"""rename Model A hand-off event 'send' -> 'send_to_ses' and move dedup index

Revision ID: j9k0l1m2n3o4
Revises: i8j9k0l1m2n3
Create Date: 2026-06-09

Model A's dispatch path historically logged its synchronous SES hand-off as
event_type='send'. That collided with the original meaning of 'send' — the
asynchronous "Send" notification emitted by the SES configuration set (via SNS) —
which migration a0b1c2d3e4f5 had deliberately split out as 'send_to_ses'.

This migration finishes that split:
  * Reclassifies every existing 'send' row to 'send_to_ses'. This is safe because
    no SNS/SES webhook is wired up yet, so every 'send' row in the table is in
    fact one of our hand-offs — not an SES-emitted notification.
  * Moves the partial UNIQUE dedup index from WHERE event_type='send' to
    WHERE event_type='send_to_ses', keeping the DB-level idempotency guarantee in
    lock-step with the renamed write (dispatch_one now writes 'send_to_ses').

After this, 'send' (plus 'delivery'/'bounce'/'complaint'/'click') is reserved for
a future SES SNS webhook and is written by no application code.

NOTE: legacy tool-approval hand-offs already use 'send_to_ses' with NULL
campaign_id/contact_id, so they fall outside the index predicate and never
collide with campaign sends.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'j9k0l1m2n3o4'
down_revision: Union[str, None] = 'i8j9k0l1m2n3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_INDEX = "uq_email_events_send_campaign_contact"
NEW_INDEX = "uq_email_events_send_to_ses_campaign_contact"


def upgrade() -> None:
    # Drop the old predicate index first so the reclassification is unconstrained.
    op.drop_index(OLD_INDEX, table_name="email_events")

    # Every existing 'send' is a hand-off (no SNS webhook exists). The old index
    # already prevented duplicate (campaign_id, contact_id) sends, so the
    # converted rows remain unique under the new predicate.
    op.execute("UPDATE email_events SET event_type = 'send_to_ses' WHERE event_type = 'send'")

    op.create_index(
        NEW_INDEX,
        "email_events",
        ["campaign_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text(
            "event_type = 'send_to_ses' AND campaign_id IS NOT NULL AND contact_id IS NOT NULL"
        ),
    )


def downgrade() -> None:
    op.drop_index(NEW_INDEX, table_name="email_events")

    # Revert only the Model A hand-offs. They always carry a campaign_id, whereas
    # legacy tool-approval 'send_to_ses' rows have NULL campaign_id and must stay
    # as 'send_to_ses' (they pre-date this migration).
    op.execute(
        "UPDATE email_events SET event_type = 'send' "
        "WHERE event_type = 'send_to_ses' AND campaign_id IS NOT NULL"
    )

    op.create_index(
        OLD_INDEX,
        "email_events",
        ["campaign_id", "contact_id"],
        unique=True,
        postgresql_where=sa.text(
            "event_type = 'send' AND campaign_id IS NOT NULL AND contact_id IS NOT NULL"
        ),
    )
