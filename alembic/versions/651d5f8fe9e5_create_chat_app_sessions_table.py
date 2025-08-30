"""create chat app sessions table

Revision ID: 651d5f8fe9e5
Revises: 7bcb977279b0
Create Date: 2025-08-30 11:30:35.042303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '651d5f8fe9e5'
down_revision: Union[str, None] = '7bcb977279b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_app_sessions',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('session_id', sa.UUID, unique=True, index=True),
        sa.Column('chat_app_id', sa.String, index=True),
        sa.Column('account_id', sa.Integer, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.func.now()),
        sa.Column('title', sa.String),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('chat_app_sessions')
