"""add_google_gmail_smtp_to_service_name_enum

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-03-29

Adds GOOGLE_GMAIL_SMTP to the service_name_enum type for storing
Gmail App Password credentials used by the sendTxtEmailWithGoogle agent tool.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's9t0u1v2w3x4'
down_revision: Union[str, None] = 'r8s9t0u1v2w3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'GOOGLE_GMAIL_SMTP'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'GOOGLE_GMAIL_SMTP';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Postgres does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
