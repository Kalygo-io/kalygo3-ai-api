"""make credentials table flexible

Revision ID: f8a3b2c1d456
Revises: 992a5aeba32a
Create Date: 2026-01-27

This migration adds flexibility to the credentials table to support:
- API keys (existing)
- Database connection strings
- OAuth credentials
- SSH keys
- Certificates
- Any other credential type

The migration:
1. Adds credential_type column to identify what kind of credential this is
2. Adds encrypted_data column to store any credential structure (JSON encrypted)
3. Adds metadata column for non-sensitive information
4. Migrates existing data from encrypted_api_key to encrypted_data
5. Keeps encrypted_api_key for backward compatibility

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f8a3b2c1d456'
down_revision: Union[str, None] = '992a5aeba32a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add new columns
    # credential_type is nullable initially - will be set by migration script
    op.add_column('credentials', 
        sa.Column('credential_type', sa.String(50), nullable=True)
    )
    op.add_column('credentials',
        sa.Column('encrypted_data', sa.Text(), nullable=True)
    )
    op.add_column('credentials',
        sa.Column('credential_metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True)
    )
    
    # Step 2: Set default credential_type for existing records
    # NOTE: This only sets the type, NOT the encrypted_data
    # Run migrate_credentials_to_flexible_format.py to properly migrate data
    connection = op.get_bind()
    connection.execute(sa.text("""
        UPDATE credentials 
        SET credential_type = 'api_key'
        WHERE credential_type IS NULL
    """))
    
    # Step 3: Make credential_type non-nullable
    op.alter_column('credentials', 'credential_type', nullable=False)
    
    # Step 4: Create index on credential_type for query performance
    op.create_index(
        op.f('ix_credentials_credential_type'), 
        'credentials', 
        ['credential_type'], 
        unique=False
    )
    
    # IMPORTANT: After running this migration, run the Python script to 
    # properly migrate encrypted data:
    #   python scripts/migrate_credentials_to_flexible_format.py


def downgrade() -> None:
    # Remove the index
    op.drop_index(op.f('ix_credentials_credential_type'), table_name='credentials')
    
    # Drop new columns
    op.drop_column('credentials', 'credential_metadata')
    op.drop_column('credentials', 'encrypted_data')
    op.drop_column('credentials', 'credential_type')
