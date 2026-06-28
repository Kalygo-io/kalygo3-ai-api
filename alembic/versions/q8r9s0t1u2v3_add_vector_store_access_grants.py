"""add_vector_store_access_grants

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-06-28

Creates the vector_store_access_grants table for sharing knowledge bases
(Pinecone indexes) with access groups. A knowledge base has no row of its own,
so the grant is keyed by the index's natural identity (owner_account_id +
index_name). Permission level is derived from the member's access-group role.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q8r9s0t1u2v3'
down_revision: Union[str, None] = 'p7q8r9s0t1u2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index(op.f('ix_vector_store_access_grants_access_group_id'), table_name='vector_store_access_grants')
    op.drop_index(op.f('ix_vector_store_access_grants_index_name'), table_name='vector_store_access_grants')
    op.drop_index(op.f('ix_vector_store_access_grants_owner_account_id'), table_name='vector_store_access_grants')
    op.drop_index(op.f('ix_vector_store_access_grants_id'), table_name='vector_store_access_grants')
    op.drop_table('vector_store_access_grants')
