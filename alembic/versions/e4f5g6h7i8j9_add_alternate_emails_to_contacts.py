"""add_alternate_emails_to_contacts

Revision ID: e4f5g6h7i8j9
Revises: d3e4f5g6h7i8
Create Date: 2026-05-19

A contact often has more than one email address (work, personal, etc.).
Adds two optional secondary email columns alongside the existing primary
`email` ("Default email" in the UI).

Both nullable so existing rows are unaffected. Not uniqueness-constrained:
unlike the primary `email`, alternates may legitimately collide (e.g. a
shared family/team inbox) and exist purely as informational + searchable
metadata — outbound campaigns continue to send only to `email`.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'e4f5g6h7i8j9'
down_revision: Union[str, None] = 'd3e4f5g6h7i8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'contacts',
        sa.Column('alt_email_1', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'contacts',
        sa.Column('alt_email_2', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('contacts', 'alt_email_2')
    op.drop_column('contacts', 'alt_email_1')
