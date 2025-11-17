"""add reset token to account table

Revision ID: 6e17f36d5886
Revises: 1cb2159cde61
Create Date: 2025-11-17 22:30:49.037686

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6e17f36d5886'
down_revision: Union[str, None] = '1cb2159cde61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
