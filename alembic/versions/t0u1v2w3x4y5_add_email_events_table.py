"""add email_events table

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None

EMAIL_EVENT_TYPE_ENUM = postgresql.ENUM(
    'send', 'delivery', 'open', 'bounce', 'complaint', 'other',
    name='emaileventtype',
    create_type=True,
)


def upgrade() -> None:
    EMAIL_EVENT_TYPE_ENUM.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'email_events',
        sa.Column('id', sa.Integer(), nullable=False),

        # Ownership / scoping
        sa.Column('account_id', sa.Integer(), nullable=False),

        # What email triggered this event
        sa.Column('tool_approval_id', sa.Integer(), nullable=True),

        # Campaign grouping (nullable until a campaigns table exists)
        sa.Column('campaign_id', sa.Integer(), nullable=True),

        # Who received the email
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('email_address', sa.String(320), nullable=False),

        # Event classification
        sa.Column(
            'event_type',
            postgresql.ENUM(
                'send', 'delivery', 'open', 'bounce', 'complaint', 'other',
                name='emaileventtype',
                create_type=False,
            ),
            nullable=False,
        ),

        # Provider info
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('provider_message_id', sa.String(255), nullable=True),

        # Arbitrary extra data (bounce codes, user-agent, link clicked, etc.)
        sa.Column('event_metadata', sa.JSON(), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),

        # Constraints
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tool_approval_id'], ['pending_tool_approvals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indexes for common dashboard query patterns
    op.create_index('ix_email_events_id', 'email_events', ['id'])
    op.create_index('ix_email_events_account_id', 'email_events', ['account_id'])
    op.create_index('ix_email_events_tool_approval_id', 'email_events', ['tool_approval_id'])
    op.create_index('ix_email_events_campaign_id', 'email_events', ['campaign_id'])
    op.create_index('ix_email_events_contact_id', 'email_events', ['contact_id'])
    op.create_index('ix_email_events_event_type', 'email_events', ['event_type'])
    op.create_index('ix_email_events_provider_message_id', 'email_events', ['provider_message_id'])
    # Composite index for the most common dashboard query: account + event_type + created_at
    op.create_index(
        'ix_email_events_account_event_type_created_at',
        'email_events',
        ['account_id', 'event_type', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_email_events_account_event_type_created_at', table_name='email_events')
    op.drop_index('ix_email_events_provider_message_id', table_name='email_events')
    op.drop_index('ix_email_events_event_type', table_name='email_events')
    op.drop_index('ix_email_events_contact_id', table_name='email_events')
    op.drop_index('ix_email_events_campaign_id', table_name='email_events')
    op.drop_index('ix_email_events_tool_approval_id', table_name='email_events')
    op.drop_index('ix_email_events_account_id', table_name='email_events')
    op.drop_index('ix_email_events_id', table_name='email_events')
    op.drop_table('email_events')
    EMAIL_EVENT_TYPE_ENUM.drop(op.get_bind(), checkfirst=True)
