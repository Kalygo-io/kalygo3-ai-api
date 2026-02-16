"""add_elevenlabs_api_key_to_service_name_enum

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-01-30

Adds ELEVENLABS_API_KEY to the service_name_enum type for storing
ElevenLabs API key credentials.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'i9j0k1l2m3n4'
down_revision: Union[str, None] = 'h8i9j0k1l2m3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add ELEVENLABS_API_KEY to the service_name_enum type
    # Check if the value already exists before adding it
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'ELEVENLABS_API_KEY' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'ELEVENLABS_API_KEY';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Note: Postgres does not support removing enum values directly.
    # To properly downgrade, we would need to:
    # 1. Convert the column back to VARCHAR
    # 2. Drop and recreate the enum without ELEVENLABS_API_KEY
    # 3. Convert back to enum
    # For now, we'll leave a comment indicating this limitation.
    # If downgrade is needed, manual intervention would be required.
    pass
