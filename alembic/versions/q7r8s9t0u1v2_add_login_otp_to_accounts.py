"""add login_otp columns to accounts

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'q7r8s9t0u1v2'
down_revision = 'p6q7r8s9t0u1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('accounts', sa.Column('login_otp', sa.String(), nullable=True))
    op.add_column('accounts', sa.Column('login_otp_expires_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('accounts', 'login_otp_expires_at')
    op.drop_column('accounts', 'login_otp')
