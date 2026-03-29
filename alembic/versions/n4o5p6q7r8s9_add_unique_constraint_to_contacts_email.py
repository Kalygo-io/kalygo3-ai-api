"""add_unique_constraint_to_contacts_email

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2026-03-29

Adds a unique constraint on the email column of the contacts table.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'n4o5p6q7r8s9'
down_revision: Union[str, None] = 'm3n4o5p6q7r8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_contacts_email', 'contacts', ['email'])


def downgrade() -> None:
    op.drop_constraint('uq_contacts_email', 'contacts', type_='unique')
