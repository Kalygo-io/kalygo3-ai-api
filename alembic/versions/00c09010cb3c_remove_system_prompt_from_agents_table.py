"""remove_system_prompt_from_agents_table

Revision ID: 00c09010cb3c
Revises: 7068c907d780
Create Date: 2026-01-17 03:50:36.500308

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00c09010cb3c'
down_revision: Union[str, None] = '7068c907d780'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the system_prompt column from agents table
    # Note: Before running this migration, ensure that any existing system_prompt values
    # have been migrated to the config field if needed.
    op.drop_column('agents', 'system_prompt')


def downgrade() -> None:
    # Add back the system_prompt column
    op.add_column('agents', sa.Column('system_prompt', sa.Text(), nullable=True))
