"""drop legacy per-resource grant tables (contract step)

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-06-28

Final "contract" step of the unified-access-grants migration. All sharing now
lives in access_grants (backfilled + verified); no code reads or writes the three
legacy tables. This drops them.

ONE-WAY for data: downgrade recreates the table STRUCTURE (so the migration
round-trips) but does NOT restore rows — recover data from a pre-drop pg_dump if
ever needed.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c0d1e2f3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('agent_access_grants')
    op.drop_table('vector_store_access_grants')
    op.drop_table('credential_access_grants')


def downgrade() -> None:
    # Structure-only recreation (no data). Mirrors the original create migrations.
    op.create_table(
        'agent_access_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('agent_id', sa.Integer(), sa.ForeignKey('agents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_group_id', sa.Integer(), sa.ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('agent_id', 'access_group_id', name='uq_agent_access_grants_agent_group'),
    )
    op.create_index(op.f('ix_agent_access_grants_id'), 'agent_access_grants', ['id'], unique=True)
    op.create_index(op.f('ix_agent_access_grants_agent_id'), 'agent_access_grants', ['agent_id'])
    op.create_index(op.f('ix_agent_access_grants_access_group_id'), 'agent_access_grants', ['access_group_id'])

    op.create_table(
        'vector_store_access_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('index_name', sa.String(), nullable=False),
        sa.Column('access_group_id', sa.Integer(), sa.ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_account_id', 'index_name', 'access_group_id', name='uq_vector_store_access_grants_owner_index_group'),
    )
    op.create_index(op.f('ix_vector_store_access_grants_id'), 'vector_store_access_grants', ['id'], unique=True)
    op.create_index(op.f('ix_vector_store_access_grants_owner_account_id'), 'vector_store_access_grants', ['owner_account_id'])
    op.create_index(op.f('ix_vector_store_access_grants_index_name'), 'vector_store_access_grants', ['index_name'])
    op.create_index(op.f('ix_vector_store_access_grants_access_group_id'), 'vector_store_access_grants', ['access_group_id'])

    op.create_table(
        'credential_access_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('credential_id', sa.Integer(), sa.ForeignKey('credentials.id', ondelete='CASCADE'), nullable=False),
        sa.Column('access_group_id', sa.Integer(), sa.ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=True),
        sa.Column('grantee_account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            '(access_group_id IS NOT NULL)::int + (grantee_account_id IS NOT NULL)::int = 1',
            name='ck_credential_grant_exactly_one_target',
        ),
    )
    op.create_index(op.f('ix_credential_access_grants_id'), 'credential_access_grants', ['id'], unique=True)
    op.create_index(op.f('ix_credential_access_grants_credential_id'), 'credential_access_grants', ['credential_id'])
    op.create_index(op.f('ix_credential_access_grants_access_group_id'), 'credential_access_grants', ['access_group_id'])
    op.create_index(op.f('ix_credential_access_grants_grantee_account_id'), 'credential_access_grants', ['grantee_account_id'])
    op.create_index(
        'uq_credential_grant_group', 'credential_access_grants',
        ['credential_id', 'access_group_id'], unique=True,
        postgresql_where=sa.text('access_group_id IS NOT NULL'),
    )
    op.create_index(
        'uq_credential_grant_account', 'credential_access_grants',
        ['credential_id', 'grantee_account_id'], unique=True,
        postgresql_where=sa.text('grantee_account_id IS NOT NULL'),
    )
