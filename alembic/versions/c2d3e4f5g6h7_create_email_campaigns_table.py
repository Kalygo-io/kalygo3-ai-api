"""create_email_campaigns_table

Revision ID: c2d3e4f5g6h7
Revises: b1c2d3e4f5g6
Create Date: 2026-04-29

Adds email_campaigns — tracks named email campaigns with a public UUID,
template, contact list, and lifecycle status. Also adds FK constraints
from email_events.campaign_id and email_campaign_ratings.campaign_id
back to this new table.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from alembic import op

revision: str = 'c2d3e4f5g6h7'
down_revision: Union[str, None] = 'b1c2d3e4f5g6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_STATUS_ENUM_NAME = 'emailcampaignstatus'


def upgrade() -> None:
    op.execute("DO $$ BEGIN "
               "CREATE TYPE emailcampaignstatus AS ENUM ('draft','active','paused','completed'); "
               "EXCEPTION WHEN duplicate_object THEN NULL; END $$")

    op.create_table(
        'email_campaigns',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', sa.UUID(), nullable=False, unique=True),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('email_template_id', sa.Integer(),
                  sa.ForeignKey('email_templates.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('contact_list_id', sa.Integer(),
                  sa.ForeignKey('contact_lists.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('status',
                  PG_ENUM('draft', 'active', 'paused', 'completed',
                          name=_STATUS_ENUM_NAME, create_type=False),
                  nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_email_campaigns_id', 'email_campaigns', ['id'])
    op.create_index('ix_email_campaigns_uuid', 'email_campaigns', ['uuid'], unique=True)
    op.create_index('ix_email_campaigns_account_id', 'email_campaigns', ['account_id'])
    op.create_index('ix_email_campaigns_status', 'email_campaigns', ['status'])
    op.create_index('ix_email_campaigns_email_template_id', 'email_campaigns', ['email_template_id'])
    op.create_index('ix_email_campaigns_contact_list_id', 'email_campaigns', ['contact_list_id'])

    # Add FK from email_events.campaign_id → email_campaigns.id
    op.create_foreign_key(
        'fk_email_events_campaign_id',
        'email_events', 'email_campaigns',
        ['campaign_id'], ['id'],
        ondelete='SET NULL',
    )

    # Add FK from email_campaign_ratings.campaign_id → email_campaigns.id
    op.create_foreign_key(
        'fk_email_campaign_ratings_campaign_id',
        'email_campaign_ratings', 'email_campaigns',
        ['campaign_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_email_campaign_ratings_campaign_id', 'email_campaign_ratings', type_='foreignkey')
    op.drop_constraint('fk_email_events_campaign_id', 'email_events', type_='foreignkey')

    op.drop_index('ix_email_campaigns_contact_list_id', 'email_campaigns')
    op.drop_index('ix_email_campaigns_email_template_id', 'email_campaigns')
    op.drop_index('ix_email_campaigns_status', 'email_campaigns')
    op.drop_index('ix_email_campaigns_account_id', 'email_campaigns')
    op.drop_index('ix_email_campaigns_uuid', 'email_campaigns')
    op.drop_index('ix_email_campaigns_id', 'email_campaigns')
    op.drop_table('email_campaigns')

    op.execute("DROP TYPE IF EXISTS emailcampaignstatus")
