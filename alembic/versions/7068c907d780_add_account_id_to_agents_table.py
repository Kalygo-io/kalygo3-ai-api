"""add_account_id_to_agents_table

Revision ID: 7068c907d780
Revises: 151b744acb62
Create Date: 2026-01-17 02:39:36.002737

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7068c907d780'
down_revision: Union[str, None] = '151b744acb62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add account_id column to agents table (nullable initially)
    op.add_column('agents', sa.Column('account_id', sa.Integer(), nullable=True))
    
    # If there are existing agents, you need to handle them first:
    # Option 1: Delete existing agents (if this is a new feature with no production data)
    # Option 2: Set a default account_id for existing agents
    # Option 3: Manually update existing agents before making NOT NULL
    
    # For now, we'll make it nullable. After handling existing data, uncomment the line below:
    # op.alter_column('agents', 'account_id', nullable=False)
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_agents_account_id',
        'agents',
        'accounts',
        ['account_id'],
        ['id']
    )
    
    # Create index on account_id
    op.create_index(op.f('ix_agents_account_id'), 'agents', ['account_id'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index(op.f('ix_agents_account_id'), table_name='agents')
    
    # Drop foreign key constraint
    op.drop_constraint('fk_agents_account_id', 'agents', type_='foreignkey')
    
    # Drop column
    op.drop_column('agents', 'account_id')
