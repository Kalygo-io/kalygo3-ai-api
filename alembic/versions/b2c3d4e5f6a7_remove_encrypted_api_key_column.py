"""remove_encrypted_api_key_column

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-27

Removes the deprecated encrypted_api_key column from the credentials table.
All credentials should now use the encrypted_data column (JSON format).

IMPORTANT: Before running this migration:
1. Ensure all credentials have been migrated to encrypted_data format
   Run: python scripts/migrate_credentials_to_flexible_format.py --verify
2. Ensure all code uses get_credential_value() instead of encrypted_api_key

This migration is NOT reversible in terms of data - the downgrade will
recreate the column but the data will be lost.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Verify all credentials have encrypted_data before dropping
    # This is a safety check - will raise if any credentials don't have encrypted_data
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT COUNT(*) FROM credentials 
        WHERE encrypted_data IS NULL AND encrypted_api_key IS NOT NULL
    """))
    count = result.scalar()
    
    if count > 0:
        raise Exception(
            f"Cannot drop encrypted_api_key: {count} credential(s) have not been migrated. "
            f"Run: python scripts/migrate_credentials_to_flexible_format.py"
        )
    
    # Drop the deprecated column
    op.drop_column('credentials', 'encrypted_api_key')


def downgrade() -> None:
    # Recreate the column (data will be lost)
    op.add_column('credentials',
        sa.Column('encrypted_api_key', sa.String(), nullable=True)
    )
    
    # Note: To restore data, you would need to:
    # 1. Decrypt encrypted_data for each credential
    # 2. Extract the api_key value
    # 3. Re-encrypt and store in encrypted_api_key
    # This is not done automatically as it requires the encryption key
