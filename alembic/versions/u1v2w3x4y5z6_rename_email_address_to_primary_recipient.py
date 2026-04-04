"""rename email_address to primary_recipient and make nullable

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = 'u1v2w3x4y5z6'
down_revision = 't0u1v2w3x4y5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'email_events',
        'email_address',
        new_column_name='primary_recipient',
        existing_type=sa.String(320),
        existing_nullable=False,
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'email_events',
        'primary_recipient',
        new_column_name='email_address',
        existing_type=sa.String(320),
        existing_nullable=True,
        nullable=False,
    )
