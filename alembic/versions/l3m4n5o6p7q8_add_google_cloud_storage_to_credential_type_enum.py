"""add_google_cloud_storage_to_credential_type_enum

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-06-21

Adds 'GOOGLE_CLOUD_STORAGE' to the credential_type_enum PostgreSQL ENUM so
accounts can store a Google Cloud Storage service-account credential via the
flexible Credentials system.
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'l3m4n5o6p7q8'
down_revision: Union[str, None] = 'k2l3m4n5o6p7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum
                WHERE enumlabel = 'GOOGLE_CLOUD_STORAGE'
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'credential_type_enum')
            ) THEN
                ALTER TYPE credential_type_enum ADD VALUE 'GOOGLE_CLOUD_STORAGE';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values directly.
    # Manual intervention required if a downgrade is needed.
    pass
