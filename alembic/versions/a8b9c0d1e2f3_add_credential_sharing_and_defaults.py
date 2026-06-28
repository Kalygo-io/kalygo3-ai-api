"""add credential sharing and per-user defaults

Revision ID: a8b9c0d1e2f3
Revises: q8r9s0t1u2v3
Create Date: 2026-06-28

Adds two tables:

- credential_access_grants: shares a credential with EITHER an access group OR an
  individual account (exactly one target, enforced by a check constraint, with
  partial unique indexes preventing duplicate shares).
- credential_defaults: a per-account, per-credential-type default selection
  (one default per type per account). The credential_id FK cascades so deleting
  a credential clears any default pointing at it.

Reuses the existing credential_type_enum PG type (create_type=False).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = 'q8r9s0t1u2v3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reference the existing PG enum without (re)creating it.
credential_type_enum = postgresql.ENUM(name='credential_type_enum', create_type=False)


def upgrade() -> None:
    # ── credential_access_grants ──────────────────────────────────────────────
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
    # Partial unique indexes: no duplicate share to the same group / same individual.
    op.create_index(
        'uq_credential_grant_group',
        'credential_access_grants',
        ['credential_id', 'access_group_id'],
        unique=True,
        postgresql_where=sa.text('access_group_id IS NOT NULL'),
    )
    op.create_index(
        'uq_credential_grant_account',
        'credential_access_grants',
        ['credential_id', 'grantee_account_id'],
        unique=True,
        postgresql_where=sa.text('grantee_account_id IS NOT NULL'),
    )

    # ── credential_defaults ───────────────────────────────────────────────────
    op.create_table(
        'credential_defaults',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('credential_type', credential_type_enum, nullable=False),
        sa.Column('credential_id', sa.Integer(), sa.ForeignKey('credentials.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('account_id', 'credential_type', name='uq_credential_default_account_type'),
    )
    op.create_index(op.f('ix_credential_defaults_id'), 'credential_defaults', ['id'], unique=True)
    op.create_index(op.f('ix_credential_defaults_account_id'), 'credential_defaults', ['account_id'])
    op.create_index(op.f('ix_credential_defaults_credential_type'), 'credential_defaults', ['credential_type'])
    op.create_index(op.f('ix_credential_defaults_credential_id'), 'credential_defaults', ['credential_id'])


def downgrade() -> None:
    op.drop_index(op.f('ix_credential_defaults_credential_id'), table_name='credential_defaults')
    op.drop_index(op.f('ix_credential_defaults_credential_type'), table_name='credential_defaults')
    op.drop_index(op.f('ix_credential_defaults_account_id'), table_name='credential_defaults')
    op.drop_index(op.f('ix_credential_defaults_id'), table_name='credential_defaults')
    op.drop_table('credential_defaults')

    op.drop_index('uq_credential_grant_account', table_name='credential_access_grants')
    op.drop_index('uq_credential_grant_group', table_name='credential_access_grants')
    op.drop_index(op.f('ix_credential_access_grants_grantee_account_id'), table_name='credential_access_grants')
    op.drop_index(op.f('ix_credential_access_grants_access_group_id'), table_name='credential_access_grants')
    op.drop_index(op.f('ix_credential_access_grants_credential_id'), table_name='credential_access_grants')
    op.drop_index(op.f('ix_credential_access_grants_id'), table_name='credential_access_grants')
    op.drop_table('credential_access_grants')
