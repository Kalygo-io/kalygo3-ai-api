"""add new usage_credits table that tracks how many credits each account has

Revision ID: 421cb8407f69
Revises: 6e17f36d5886
Create Date: 2025-11-17 22:32:05.095642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '421cb8407f69'
down_revision: Union[str, None] = '6e17f36d5886'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usage_credits',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('account_id', sa.Integer, nullable=False, index=True),
        sa.Column('amount', sa.Float, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('usage_credits')
