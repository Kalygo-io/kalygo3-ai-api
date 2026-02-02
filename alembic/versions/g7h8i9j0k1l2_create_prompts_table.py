"""create_prompts_table

Revision ID: g7h8i9j0k1l2
Revises: f8a3b2c1d456
Create Date: 2026-01-30

Creates the prompts table for storing reusable prompt templates.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prompts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create indexes
    op.create_index(op.f('ix_prompts_id'), 'prompts', ['id'], unique=True)
    op.create_index(op.f('ix_prompts_account_id'), 'prompts', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_prompts_account_id'), table_name='prompts')
    op.drop_index(op.f('ix_prompts_id'), table_name='prompts')
    op.drop_table('prompts')
