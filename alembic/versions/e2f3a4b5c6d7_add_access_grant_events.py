"""add access_grant_events (append-only access audit log)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-06-28

Append-only log of access-grant changes (create / revoke / role_change) with the
acting account and snapshotted human-readable context. Independent of
access_grants (no FKs) so it survives revocation and renames.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'access_grant_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(length=20), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('resource_label', sa.String(length=512), nullable=True),
        sa.Column('principal_type', sa.String(length=20), nullable=False),
        sa.Column('principal_id', sa.Integer(), nullable=False),
        sa.Column('principal_label', sa.String(length=512), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=True),
        sa.Column('actor_account_id', sa.Integer(), nullable=True),
        sa.Column('actor_email', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("event_type IN ('create','revoke','role_change')", name='ck_access_grant_event_type'),
    )
    op.create_index(op.f('ix_access_grant_events_id'), 'access_grant_events', ['id'], unique=True)
    op.create_index(op.f('ix_access_grant_events_event_type'), 'access_grant_events', ['event_type'])
    op.create_index(op.f('ix_access_grant_events_actor_account_id'), 'access_grant_events', ['actor_account_id'])
    op.create_index(op.f('ix_access_grant_events_created_at'), 'access_grant_events', ['created_at'])
    op.create_index('ix_access_grant_events_resource', 'access_grant_events', ['resource_type', 'resource_id'])


def downgrade() -> None:
    op.drop_index('ix_access_grant_events_resource', table_name='access_grant_events')
    op.drop_index(op.f('ix_access_grant_events_created_at'), table_name='access_grant_events')
    op.drop_index(op.f('ix_access_grant_events_actor_account_id'), table_name='access_grant_events')
    op.drop_index(op.f('ix_access_grant_events_event_type'), table_name='access_grant_events')
    op.drop_index(op.f('ix_access_grant_events_id'), table_name='access_grant_events')
    op.drop_table('access_grant_events')
