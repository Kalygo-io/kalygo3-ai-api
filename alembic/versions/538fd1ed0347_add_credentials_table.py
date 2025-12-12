"""add credentials table

Revision ID: 538fd1ed0347
Revises: 421cb8407f69
Create Date: 2025-12-12 17:43:32.698208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '538fd1ed0347'
down_revision: Union[str, None] = '421cb8407f69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create credentials table only
    op.create_table('credentials',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('service_name', sa.String(), nullable=False),
    sa.Column('encrypted_api_key', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_credentials_account_id'), 'credentials', ['account_id'], unique=False)
    op.create_index(op.f('ix_credentials_id'), 'credentials', ['id'], unique=False)
    op.create_index(op.f('ix_credentials_service_name'), 'credentials', ['service_name'], unique=False)


def downgrade() -> None:
    # Drop credentials table only
    op.drop_index(op.f('ix_credentials_service_name'), table_name='credentials')
    op.drop_index(op.f('ix_credentials_id'), table_name='credentials')
    op.drop_index(op.f('ix_credentials_account_id'), table_name='credentials')
    op.drop_table('credentials')
