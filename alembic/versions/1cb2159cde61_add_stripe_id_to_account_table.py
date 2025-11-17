"""add stripe id to account table

Revision ID: 1cb2159cde61
Revises: 62968f1e398c
Create Date: 2025-11-17 18:43:33.924817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1cb2159cde61'
down_revision: Union[str, None] = '62968f1e398c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add stripe_id column to accounts table
    op.add_column('accounts', sa.Column('stripe_customer_id', sa.String, nullable=True))


def downgrade() -> None:
    # Remove stripe_id column from accounts table
    op.drop_column('accounts', 'stripe_customer_id')
