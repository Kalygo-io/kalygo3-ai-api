"""rename_provider_message_id_to_message_id

Revision ID: w3x4y5z6a7b8
Revises: v2w3x4y5z6a7
Create Date: 2026-04-04

Renames email_events.provider_message_id → message_id for brevity.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'w3x4y5z6a7b8'
down_revision: Union[str, None] = 'v2w3x4y5z6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'email_events',
        'provider_message_id',
        new_column_name='message_id',
        existing_type=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'email_events',
        'message_id',
        new_column_name='provider_message_id',
        existing_type=sa.String(255),
        existing_nullable=True,
    )
