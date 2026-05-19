"""add_contact_id_to_chat_sessions

Revision ID: d3e4f5g6h7i8
Revises: c2d3e4f5g6h7
Create Date: 2026-05-18

Adds an optional contact_id to chat_sessions so a chat session can be bound
to a single CRM contact. This binding is the server-trusted scope for the
contact-scoped agent drawer: scoped tools run against this contact only.

Nullable so existing/general sessions are unaffected. ON DELETE SET NULL so
deleting a contact preserves its chat history while clearing the scope —
which makes the contact-scoped agent fail closed rather than run unscoped.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'd3e4f5g6h7i8'
down_revision: Union[str, None] = 'c2d3e4f5g6h7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'chat_sessions',
        sa.Column('contact_id', sa.Integer(),
                  sa.ForeignKey('contacts.id', ondelete='SET NULL'),
                  nullable=True),
    )
    op.create_index(
        'ix_chat_sessions_contact_id', 'chat_sessions', ['contact_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_chat_sessions_contact_id', table_name='chat_sessions')
    op.drop_column('chat_sessions', 'contact_id')
