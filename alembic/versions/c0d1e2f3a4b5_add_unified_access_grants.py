"""add unified access_grants table + backfill from per-resource grant tables

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-06-28

Introduces the unified access_grants table (principal × resource × role) and
backfills it from the three existing grant tables, preserving current effective
access. The old tables are LEFT IN PLACE (dormant) and dropped in a later
contract migration once the unified model is verified in production.

Backfill mapping:
- agent_access_grants            -> (group,   agent,        'use')
- credential_access_grants       -> (group|account, credential, 'use')
- vector_store_access_grants     -> (group,   vector_store, 'read')
    + per current group-admin    -> (account, vector_store, 'write')
  (old model derived write from the group-admin role; the new model makes it an
   explicit per-principal grant, so "members view, admins edit" is preserved.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c0d1e2f3a4b5'
down_revision: Union[str, None] = 'b9c0d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'access_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('principal_type', sa.String(length=20), nullable=False),
        sa.Column('principal_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='read'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('principal_type', 'principal_id', 'resource_type', 'resource_id',
                            name='uq_access_grant_principal_resource'),
        sa.CheckConstraint("principal_type IN ('account','group')", name='ck_access_grant_principal_type'),
        sa.CheckConstraint("resource_type IN ('agent','vector_store','credential')", name='ck_access_grant_resource_type'),
        sa.CheckConstraint("role IN ('read','write','use')", name='ck_access_grant_role'),
    )
    op.create_index(op.f('ix_access_grants_id'), 'access_grants', ['id'], unique=True)
    op.create_index('ix_access_grants_resource', 'access_grants', ['resource_type', 'resource_id'])
    op.create_index('ix_access_grants_principal', 'access_grants', ['principal_type', 'principal_id'])

    # ── Backfill ──────────────────────────────────────────────────────────────
    # Agents: group -> use
    op.execute(
        """
        INSERT INTO access_grants (principal_type, principal_id, resource_type, resource_id, role, created_at, updated_at)
        SELECT 'group', access_group_id, 'agent', agent_id, 'use', now(), now()
        FROM agent_access_grants
        ON CONFLICT (principal_type, principal_id, resource_type, resource_id) DO NOTHING
        """
    )
    # Credentials: group -> use
    op.execute(
        """
        INSERT INTO access_grants (principal_type, principal_id, resource_type, resource_id, role, created_at, updated_at)
        SELECT 'group', access_group_id, 'credential', credential_id, 'use', now(), now()
        FROM credential_access_grants
        WHERE access_group_id IS NOT NULL
        ON CONFLICT (principal_type, principal_id, resource_type, resource_id) DO NOTHING
        """
    )
    # Credentials: individual -> use
    op.execute(
        """
        INSERT INTO access_grants (principal_type, principal_id, resource_type, resource_id, role, created_at, updated_at)
        SELECT 'account', grantee_account_id, 'credential', credential_id, 'use', now(), now()
        FROM credential_access_grants
        WHERE grantee_account_id IS NOT NULL
        ON CONFLICT (principal_type, principal_id, resource_type, resource_id) DO NOTHING
        """
    )
    # Vector stores: group -> read (resource_id resolved via vector_stores row)
    op.execute(
        """
        INSERT INTO access_grants (principal_type, principal_id, resource_type, resource_id, role, created_at, updated_at)
        SELECT 'group', g.access_group_id, 'vector_store', vs.id, 'read', now(), now()
        FROM vector_store_access_grants g
        JOIN vector_stores vs
          ON vs.owner_account_id = g.owner_account_id AND vs.index_name = g.index_name
        ON CONFLICT (principal_type, principal_id, resource_type, resource_id) DO NOTHING
        """
    )
    # Vector stores: each current group-admin -> write (preserves derived write access)
    op.execute(
        """
        INSERT INTO access_grants (principal_type, principal_id, resource_type, resource_id, role, created_at, updated_at)
        SELECT DISTINCT 'account', m.account_id, 'vector_store', vs.id, 'write', now(), now()
        FROM vector_store_access_grants g
        JOIN vector_stores vs
          ON vs.owner_account_id = g.owner_account_id AND vs.index_name = g.index_name
        JOIN access_group_members m
          ON m.access_group_id = g.access_group_id AND m.role = 'admin'
        ON CONFLICT (principal_type, principal_id, resource_type, resource_id)
          DO UPDATE SET role = 'write', updated_at = now()
        """
    )


def downgrade() -> None:
    op.drop_index('ix_access_grants_principal', table_name='access_grants')
    op.drop_index('ix_access_grants_resource', table_name='access_grants')
    op.drop_index(op.f('ix_access_grants_id'), table_name='access_grants')
    op.drop_table('access_grants')
