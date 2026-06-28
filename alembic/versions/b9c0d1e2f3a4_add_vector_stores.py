"""add vector_stores (knowledge-base records with explicit credential bindings)

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-06-28

Introduces a row per knowledge base (Pinecone index) owned by an account, giving
its Pinecone/GCS credentials an explicit home. Credential FKs are nullable
(ON DELETE SET NULL); a null binding falls back to the owner's default for that
type (see services/vector_store_credentials.py).

Backfills one row per distinct (account_id, index_name) already present in
vector_db_ingestion_log and in vector_store_access_grants, leaving credential ids
NULL so existing indexes keep resolving via the owner's default until an owner
sets an explicit binding.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9c0d1e2f3a4'
down_revision: Union[str, None] = 'a8b9c0d1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'vector_stores',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('owner_account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('index_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('pinecone_credential_id', sa.Integer(), sa.ForeignKey('credentials.id', ondelete='SET NULL'), nullable=True),
        sa.Column('gcs_credential_id', sa.Integer(), sa.ForeignKey('credentials.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('owner_account_id', 'index_name', name='uq_vector_store_owner_index'),
    )
    op.create_index(op.f('ix_vector_stores_id'), 'vector_stores', ['id'], unique=True)
    op.create_index(op.f('ix_vector_stores_owner_account_id'), 'vector_stores', ['owner_account_id'])
    op.create_index(op.f('ix_vector_stores_index_name'), 'vector_stores', ['index_name'])
    op.create_index(op.f('ix_vector_stores_pinecone_credential_id'), 'vector_stores', ['pinecone_credential_id'])
    op.create_index(op.f('ix_vector_stores_gcs_credential_id'), 'vector_stores', ['gcs_credential_id'])

    # Backfill one row per distinct (account, index) already known, from both the
    # ingestion log and the access grants. ON CONFLICT keeps it idempotent and
    # avoids duplicating the union. Credential bindings stay NULL (→ default).
    op.execute(
        """
        INSERT INTO vector_stores (owner_account_id, index_name, created_at, updated_at)
        SELECT DISTINCT account_id, index_name, now(), now()
        FROM vector_db_ingestion_log
        WHERE account_id IS NOT NULL AND index_name IS NOT NULL
        ON CONFLICT (owner_account_id, index_name) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO vector_stores (owner_account_id, index_name, created_at, updated_at)
        SELECT DISTINCT owner_account_id, index_name, now(), now()
        FROM vector_store_access_grants
        WHERE owner_account_id IS NOT NULL AND index_name IS NOT NULL
        ON CONFLICT (owner_account_id, index_name) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_vector_stores_gcs_credential_id'), table_name='vector_stores')
    op.drop_index(op.f('ix_vector_stores_pinecone_credential_id'), table_name='vector_stores')
    op.drop_index(op.f('ix_vector_stores_index_name'), table_name='vector_stores')
    op.drop_index(op.f('ix_vector_stores_owner_account_id'), table_name='vector_stores')
    op.drop_index(op.f('ix_vector_stores_id'), table_name='vector_stores')
    op.drop_table('vector_stores')
