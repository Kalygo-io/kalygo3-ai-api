"""add_pinecone_api_key_to_service_name_enum

Revision ID: 166bbf223e15
Revises: 52157e901bff
Create Date: 2025-12-13 23:27:47.441214

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '166bbf223e15'
down_revision: Union[str, None] = '52157e901bff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add PINECONE_API_KEY to the service_name_enum type
    # Check if the value already exists before adding it
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'PINECONE_API_KEY' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'PINECONE_API_KEY';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Note: Postgres does not support removing enum values directly.
    # To properly downgrade, we would need to:
    # 1. Convert the column back to VARCHAR
    # 2. Drop and recreate the enum without PINECONE_API_KEY
    # 3. Convert back to enum
    # For now, we'll leave a comment indicating this limitation.
    # If downgrade is needed, manual intervention would be required.
    pass
