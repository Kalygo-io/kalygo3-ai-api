"""create_email_campaign_ratings_table

Revision ID: b1c2d3e4f5g6
Revises: a0b1c2d3e4f5
Create Date: 2026-04-29

Adds email_campaign_ratings — stores star ratings (1-5) submitted by
email recipients. Each row ties a rating to the campaign, template,
and contact that produced it. Uniqueness on tracking_id ensures one
rating per email send.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'b1c2d3e4f5g6'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_campaign_ratings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=True),
        sa.Column('email_template_id', sa.Integer(),
                  sa.ForeignKey('email_templates.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('contact_id', sa.Integer(),
                  sa.ForeignKey('contacts.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('primary_recipient', sa.String(320), nullable=True),
        sa.Column('tracking_id', sa.String(255), nullable=False, unique=True),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_email_campaign_ratings_id', 'email_campaign_ratings', ['id'])
    op.create_index('ix_email_campaign_ratings_account_id', 'email_campaign_ratings', ['account_id'])
    op.create_index('ix_email_campaign_ratings_campaign_id', 'email_campaign_ratings', ['campaign_id'])
    op.create_index('ix_email_campaign_ratings_email_template_id', 'email_campaign_ratings', ['email_template_id'])
    op.create_index('ix_email_campaign_ratings_contact_id', 'email_campaign_ratings', ['contact_id'])
    op.create_index('ix_email_campaign_ratings_tracking_id', 'email_campaign_ratings', ['tracking_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_email_campaign_ratings_tracking_id', 'email_campaign_ratings')
    op.drop_index('ix_email_campaign_ratings_contact_id', 'email_campaign_ratings')
    op.drop_index('ix_email_campaign_ratings_email_template_id', 'email_campaign_ratings')
    op.drop_index('ix_email_campaign_ratings_campaign_id', 'email_campaign_ratings')
    op.drop_index('ix_email_campaign_ratings_account_id', 'email_campaign_ratings')
    op.drop_index('ix_email_campaign_ratings_id', 'email_campaign_ratings')
    op.drop_table('email_campaign_ratings')
