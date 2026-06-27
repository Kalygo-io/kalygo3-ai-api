"""drop similarity_score from logins table

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-06-27

Removes the now-unused similarity_score column from the logins table.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o6p7q8r9s0t1'
down_revision: Union[str, None] = 'n5o6p7q8r9s0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('logins', 'similarity_score')


def downgrade() -> None:
    op.add_column('logins', sa.Column('similarity_score', sa.Double(), nullable=True))
