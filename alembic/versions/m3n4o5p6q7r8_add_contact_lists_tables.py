"""add_contact_lists_tables

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2026-03-29

Adds two new tables for the Contact Lists feature:
  - contact_lists: named subsets of contacts (name, description, account scoped)
  - contact_list_members: join table linking contact_lists ↔ contacts
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'l2m3n4o5p6q7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contact_lists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_contact_lists_id', 'contact_lists', ['id'])
    op.create_index('ix_contact_lists_account_id', 'contact_lists', ['account_id'])
    op.create_index('ix_contact_lists_created_at', 'contact_lists', ['created_at'])

    op.create_table(
        'contact_list_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_list_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contact_list_id'], ['contact_lists.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_list_id', 'contact_id', name='uq_contact_list_member'),
    )
    op.create_index('ix_contact_list_members_id', 'contact_list_members', ['id'])
    op.create_index('ix_contact_list_members_contact_list_id', 'contact_list_members', ['contact_list_id'])
    op.create_index('ix_contact_list_members_contact_id', 'contact_list_members', ['contact_id'])
    op.create_index('ix_contact_list_members_account_id', 'contact_list_members', ['account_id'])


def downgrade() -> None:
    op.drop_table('contact_list_members')
    op.drop_table('contact_lists')
