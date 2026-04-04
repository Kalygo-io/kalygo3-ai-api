"""add_click_to_emaileventtype_enum

Revision ID: v2w3x4y5z6a7
Revises: u1v2w3x4y5z6
Create Date: 2026-04-04

Adds 'click' to the emaileventtype PostgreSQL ENUM.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'v2w3x4y5z6a7'
down_revision: Union[str, None] = 'u1v2w3x4y5z6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'click'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'emaileventtype')
            ) THEN
                ALTER TYPE emaileventtype ADD VALUE 'click';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
