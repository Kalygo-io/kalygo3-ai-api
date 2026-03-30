"""add_aws_ses_to_service_name_enum

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-03-30

Adds AWS_SES to the service_name_enum type for storing
Amazon SES credentials used by the sendTxtEmail agent tool.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o5p6q7r8s9t0'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add AWS_SES to the service_name_enum type
    # Check if the value already exists before adding it
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'AWS_SES' 
                AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'service_name_enum')
            ) THEN
                ALTER TYPE service_name_enum ADD VALUE 'AWS_SES';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Note: Postgres does not support removing enum values directly.
    # To properly downgrade, we would need to:
    # 1. Convert the column back to VARCHAR
    # 2. Drop and recreate the enum without AWS_SES
    # 3. Convert back to enum
    # For now, manual intervention is required if a downgrade is needed.
    pass
