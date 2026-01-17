"""create_api_keys_table

Revision ID: abc123def456
Revises: 00c09010cb3c
Create Date: 2026-01-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, None] = '00c09010cb3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type for API key status
    op.execute("CREATE TYPE api_key_status_enum AS ENUM ('active', 'revoked')")
    
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('key_hash', sa.String(), nullable=False),
        sa.Column('key_prefix', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'revoked', name='api_key_status_enum', create_type=False), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_api_keys_id'), 'api_keys', ['id'], unique=False)
    op.create_index(op.f('ix_api_keys_account_id'), 'api_keys', ['account_id'], unique=False)
    op.create_index(op.f('ix_api_keys_key_hash'), 'api_keys', ['key_hash'], unique=True)
    op.create_index(op.f('ix_api_keys_key_prefix'), 'api_keys', ['key_prefix'], unique=False)
    op.create_index(op.f('ix_api_keys_status'), 'api_keys', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_api_keys_status'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_prefix'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_key_hash'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_account_id'), table_name='api_keys')
    op.drop_index(op.f('ix_api_keys_id'), table_name='api_keys')
    
    # Drop table
    op.drop_table('api_keys')
    
    # Drop enum type
    op.execute("DROP TYPE api_key_status_enum")
