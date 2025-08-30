"""create chat_app_messages table

Revision ID: 62968f1e398c
Revises: 651d5f8fe9e5
Create Date: 2025-08-30 18:45:42.912986

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '62968f1e398c'
down_revision: Union[str, None] = '651d5f8fe9e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'chat_app_messages',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('chat_app_session_id', sa.Integer, nullable=False, index=True),
        sa.Column('message', sa.JSON),
        sa.Column('created_at', sa.DateTime(timezone=True), default=sa.func.now()),
        sa.ForeignKeyConstraint(['chat_app_session_id'], ['chat_app_sessions.id'], ondelete='CASCADE')
    )


def downgrade() -> None:
    op.drop_table('chat_app_messages')
