"""create career_timeline table

Revision ID: c9d0e1f2g3h4
Revises: b8c9d0e1f2g3
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2g3h4'
down_revision = 'b8c9d0e1f2g3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'career_timeline',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('contact_id', sa.Integer(), sa.ForeignKey('contacts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_career_timeline_contact_id', 'career_timeline', ['contact_id'])
    op.create_index('ix_career_timeline_account_id', 'career_timeline', ['account_id'])
    op.create_index('ix_career_timeline_start_date', 'career_timeline', ['start_date'])


def downgrade() -> None:
    op.drop_index('ix_career_timeline_start_date', table_name='career_timeline')
    op.drop_index('ix_career_timeline_account_id', table_name='career_timeline')
    op.drop_index('ix_career_timeline_contact_id', table_name='career_timeline')
    op.drop_table('career_timeline')
