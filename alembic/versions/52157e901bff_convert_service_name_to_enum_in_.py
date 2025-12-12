"""convert service_name to enum in credentials table

Revision ID: 52157e901bff
Revises: 538fd1ed0347
Create Date: 2025-12-12 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '52157e901bff'
down_revision: Union[str, None] = '538fd1ed0347'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the enum type
    service_name_enum = postgresql.ENUM(
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
        name='service_name_enum',
        create_type=True
    )
    service_name_enum.create(op.get_bind(), checkfirst=True)
    
    # Alter the column to use the enum type
    # First, ensure any existing data matches the enum values (if there is any)
    op.execute("""
        UPDATE credentials 
        SET service_name = UPPER(service_name)
        WHERE service_name IS NOT NULL
    """)
    
    # Convert the column to use the enum type
    op.execute("""
        ALTER TABLE credentials 
        ALTER COLUMN service_name TYPE service_name_enum 
        USING service_name::service_name_enum
    """)


def downgrade() -> None:
    # Convert enum back to string
    op.execute("""
        ALTER TABLE credentials 
        ALTER COLUMN service_name TYPE VARCHAR 
        USING service_name::VARCHAR
    """)
    
    # Drop the enum type
    op.execute("DROP TYPE IF EXISTS service_name_enum")
