"""rename service_name col to credential_type, credential_type col to auth_type, add credential_name

Revision ID: y5z6a7b8c9d0
Revises: x4y5z6a7b8c9
Create Date: 2026-04-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'y5z6a7b8c9d0'
down_revision = 'x4y5z6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Free up the 'credential_type' column name by renaming it to 'auth_type'
    op.alter_column('credentials', 'credential_type', new_column_name='auth_type')

    # 2. Rename 'service_name' → 'credential_type'
    op.alter_column('credentials', 'service_name', new_column_name='credential_type')

    # 3. Rename the PostgreSQL enum type
    op.execute("ALTER TYPE service_name_enum RENAME TO credential_type_enum")

    # 4. Add the new credential_name column
    op.add_column(
        'credentials',
        sa.Column('credential_name', sa.String(255), nullable=True),
    )
    op.create_index('ix_credentials_credential_name', 'credentials', ['account_id', 'credential_name'])


def downgrade() -> None:
    op.drop_index('ix_credentials_credential_name', 'credentials')
    op.drop_column('credentials', 'credential_name')

    op.execute("ALTER TYPE credential_type_enum RENAME TO service_name_enum")

    op.alter_column('credentials', 'credential_type', new_column_name='service_name')
    op.alter_column('credentials', 'auth_type', new_column_name='credential_type')
