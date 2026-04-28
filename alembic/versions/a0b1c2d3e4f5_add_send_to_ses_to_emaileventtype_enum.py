"""add_send_to_ses_to_emaileventtype_enum

Revision ID: a0b1c2d3e4f5
Revises: z6a7b8c9d0e1
Create Date: 2026-04-27

Adds 'send_to_ses' to the emaileventtype PostgreSQL ENUM.

This differentiates the event logged by the API when it hands an email off
to SES (send_to_ses) from the 'send' event later emitted by the SES
configuration set, which were previously conflated.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, None] = 'c9d0e1f2g3h4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'send_to_ses'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'emaileventtype')
            ) THEN
                ALTER TYPE emaileventtype ADD VALUE 'send_to_ses';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
