"""add credential_id and sender_domain to email_events

Revision ID: z6a7b8c9d0e1
Revises: y5z6a7b8c9d0
Create Date: 2026-04-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'z6a7b8c9d0e1'
down_revision = 'y5z6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'email_events',
        sa.Column('credential_id', sa.Integer(), sa.ForeignKey('credentials.id', ondelete='SET NULL'), nullable=True),
    )
    op.add_column(
        'email_events',
        sa.Column('sender_domain', sa.String(255), nullable=True),
    )
    op.create_index('ix_email_events_credential_id', 'email_events', ['credential_id'])
    op.create_index('ix_email_events_sender_domain', 'email_events', ['sender_domain'])


def downgrade() -> None:
    op.drop_index('ix_email_events_sender_domain', table_name='email_events')
    op.drop_index('ix_email_events_credential_id', table_name='email_events')
    op.drop_column('email_events', 'sender_domain')
    op.drop_column('email_events', 'credential_id')
