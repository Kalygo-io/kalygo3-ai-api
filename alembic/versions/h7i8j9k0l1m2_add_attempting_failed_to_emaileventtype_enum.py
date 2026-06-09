"""add_attempting_failed_to_emaileventtype_enum

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-06-09

Adds 'attempting' and 'failed' to the emaileventtype PostgreSQL ENUM so the
Model A send path can record the in-flight and failed phases of a send in the
ledger (attempting before the SES call, failed if SES raises). The confirmed
phase reuses the existing 'send' value, which is also the idempotency anchor.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'h7i8j9k0l1m2'
down_revision: Union[str, None] = 'g6h7i8j9k0l1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("attempting", "failed"):
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_enum
                    WHERE enumlabel = '{value}'
                    AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'emaileventtype')
                ) THEN
                    ALTER TYPE emaileventtype ADD VALUE '{value}';
                END IF;
            END $$;
        """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
