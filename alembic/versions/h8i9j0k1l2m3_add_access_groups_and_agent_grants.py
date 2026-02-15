"""add_access_groups_and_agent_grants

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-01-30

Creates the access_groups, access_group_members, and agent_access_grants
tables for sharing agents with groups of accounts.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h8i9j0k1l2m3'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- access_groups ---
    op.create_table(
        'access_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('owner_account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_access_groups_id'), 'access_groups', ['id'], unique=True)
    op.create_index(op.f('ix_access_groups_owner_account_id'), 'access_groups', ['owner_account_id'])

    # --- access_group_members ---
    op.create_table(
        'access_group_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('access_group_id', sa.Integer(), sa.ForeignKey('access_groups.id', ondelete='CASCADE'), nullable=False),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('access_group_id', 'account_id', name='uq_access_group_members_group_account'),
    )
    op.create_index(op.f('ix_access_group_members_id'), 'access_group_members', ['id'], unique=True)
    op.create_index(op.f('ix_access_group_members_access_group_id'), 'access_group_members', ['access_group_id'])
    op.create_index(op.f('ix_access_group_members_account_id'), 'access_group_members', ['account_id'])

    # --- agent_access_grants ---
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


def downgrade() -> None:
    # agent_access_grants
    op.drop_index(op.f('ix_agent_access_grants_access_group_id'), table_name='agent_access_grants')
    op.drop_index(op.f('ix_agent_access_grants_agent_id'), table_name='agent_access_grants')
    op.drop_index(op.f('ix_agent_access_grants_id'), table_name='agent_access_grants')
    op.drop_table('agent_access_grants')

    # access_group_members
    op.drop_index(op.f('ix_access_group_members_account_id'), table_name='access_group_members')
    op.drop_index(op.f('ix_access_group_members_access_group_id'), table_name='access_group_members')
    op.drop_index(op.f('ix_access_group_members_id'), table_name='access_group_members')
    op.drop_table('access_group_members')

    # access_groups
    op.drop_index(op.f('ix_access_groups_owner_account_id'), table_name='access_groups')
    op.drop_index(op.f('ix_access_groups_id'), table_name='access_groups')
    op.drop_table('access_groups')
