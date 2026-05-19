"""create_deals_table

Revision ID: f5g6h7i8j9k0
Revises: e4f5g6h7i8j9
Create Date: 2026-05-19

Adds the `deals` table for tracking CRM sales opportunities.

A deal always belongs to an account (CASCADE). The contact link is optional
(nullable, ON DELETE SET NULL) so a deal can exist before it's tied to a
person and is preserved — not deleted — if that contact is later removed.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'f5g6h7i8j9k0'
down_revision: Union[str, None] = 'e4f5g6h7i8j9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'deals',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'account_id', sa.Integer(),
            sa.ForeignKey('accounts.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column(
            'contact_id', sa.Integer(),
            sa.ForeignKey('contacts.id', ondelete='SET NULL'),
            nullable=True, index=True,
        ),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('stage', sa.String(length=50), nullable=False, server_default='lead', index=True),
        sa.Column('expected_close_date', sa.Date(), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False, index=True,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table('deals')
