"""drop company, title, status, notes from contacts

Revision ID: b8c9d0e1f2g3
Revises: a7b8c9d0e1f2
Create Date: 2026-04-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2g3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_contacts_company', table_name='contacts')
    op.drop_index('ix_contacts_status', table_name='contacts')
    op.drop_column('contacts', 'company')
    op.drop_column('contacts', 'title')
    op.drop_column('contacts', 'status')
    op.drop_column('contacts', 'notes')


def downgrade() -> None:
    op.add_column('contacts', sa.Column('notes', sa.Text(), nullable=True))
    op.add_column('contacts', sa.Column('status', sa.String(50), nullable=True))
    op.add_column('contacts', sa.Column('title', sa.String(255), nullable=True))
    op.add_column('contacts', sa.Column('company', sa.String(255), nullable=True))
    op.create_index('ix_contacts_status', 'contacts', ['status'])
    op.create_index('ix_contacts_company', 'contacts', ['company'])
