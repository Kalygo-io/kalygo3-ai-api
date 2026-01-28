"""Add newsletter_subscribed to accounts table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-01-28 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add newsletter_subscribed column to accounts table
    # Defaults to False for existing and new accounts
    op.add_column('accounts', sa.Column('newsletter_subscribed', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('accounts', 'newsletter_subscribed')
