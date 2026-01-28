"""Add chat_session_id to leads table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-27 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add chat_session_id column to leads table
    # This references the UUID of the chat session where the lead was captured
    op.add_column('leads', sa.Column('chat_session_id', UUID(), nullable=True))
    
    # Create index for efficient lookups by chat session
    op.create_index('ix_leads_chat_session_id', 'leads', ['chat_session_id'])


def downgrade() -> None:
    # Drop the index
    op.drop_index('ix_leads_chat_session_id', table_name='leads')
    
    # Drop the column
    op.drop_column('leads', 'chat_session_id')
