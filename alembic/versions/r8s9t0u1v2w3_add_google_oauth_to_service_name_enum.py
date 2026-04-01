"""add_google_oauth_to_service_name_enum

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-03-29

Adds GOOGLE_OAUTH to the service_name_enum type for storing
Google OAuth credentials used by the sendTxtEmailWithGoogle agent tool.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r8s9t0u1v2w3'
down_revision: Union[str, None] = 'q7r8s9t0u1v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'GOOGLE_OAUTH' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'GOOGLE_OAUTH';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Postgres does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
