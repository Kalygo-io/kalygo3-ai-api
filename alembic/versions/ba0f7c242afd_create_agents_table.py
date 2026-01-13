"""create agents table

Revision ID: ba0f7c242afd
Revises: 0b18dee79020
Create Date: 2026-01-13 16:47:11.462290

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ba0f7c242afd'
down_revision: Union[str, None] = '0b18dee79020'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the agents table
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('config', postgresql.JSONB, nullable=True),
    )
    
    # Create indexes
    op.create_index(op.f('ix_agents_id'), 'agents', ['id'], unique=False)
    op.create_index(op.f('ix_agents_name'), 'agents', ['name'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_agents_name'), table_name='agents')
    op.drop_index(op.f('ix_agents_id'), table_name='agents')
    
    # Drop table
    op.drop_table('agents')
