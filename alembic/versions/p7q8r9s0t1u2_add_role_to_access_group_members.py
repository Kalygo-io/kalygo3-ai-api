"""add role to access_group_members

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p7q8r9s0t1u2'
down_revision: Union[str, None] = 'o6p7q8r9s0t1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Co-admin support: 'admin' members can co-manage the group, 'member' is a
    # plain member. Existing rows backfill to 'member' via the server default.
    op.add_column(
        'access_group_members',
        sa.Column('role', sa.String(length=50), nullable=False, server_default='member'),
    )


def downgrade() -> None:
    op.drop_column('access_group_members', 'role')
