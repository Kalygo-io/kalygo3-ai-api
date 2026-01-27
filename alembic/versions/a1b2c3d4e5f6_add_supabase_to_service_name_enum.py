"""add_supabase_to_service_name_enum

Revision ID: a1b2c3d4e5f6
Revises: f8a3b2c1d456
Create Date: 2026-01-27

Adds SUPABASE to the service_name_enum type for storing Supabase
database connection credentials.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f8a3b2c1d456'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add SUPABASE to the service_name_enum type
    # Check if the value already exists before adding it
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'SUPABASE' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'SUPABASE';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Note: Postgres does not support removing enum values directly.
    # To properly downgrade, we would need to:
    # 1. Convert the column back to VARCHAR
    # 2. Drop and recreate the enum without SUPABASE
    # 3. Convert back to enum
    # For now, we'll leave a comment indicating this limitation.
    # If downgrade is needed, manual intervention would be required.
    pass
