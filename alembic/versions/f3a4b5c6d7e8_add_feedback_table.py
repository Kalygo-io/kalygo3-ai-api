"""add feedback table (public branded-UI feedback)

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-06-28

Stores user feedback submitted from branded front-ends (e.g. bolay.kalygo.io).
Submissions are public and account-less; `client` records which branded UI the
feedback originated from so a single table can serve multiple front-ends.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client', sa.String(length=64), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_feedback_client'), 'feedback', ['client'])
    op.create_index('ix_feedback_client_created_at', 'feedback', ['client', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_feedback_client_created_at', table_name='feedback')
    op.drop_index(op.f('ix_feedback_client'), table_name='feedback')
    op.drop_table('feedback')
