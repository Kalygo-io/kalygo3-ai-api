"""create_companies_and_company_contacts_tables

Revision ID: k2l3m4n5o6p7
Revises: j9k0l1m2n3o4
Create Date: 2026-06-21

Adds the `companies` table for tracking CRM organizations and the
`company_contacts` join table linking companies to contacts (many-to-many).

A company always belongs to an account (CASCADE). A contact can be associated
with many companies and vice versa via `company_contacts`; deleting either side
removes the association rows (CASCADE) but never the company or contact itself.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'k2l3m4n5o6p7'
down_revision: Union[str, None] = 'j9k0l1m2n3o4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'companies',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'account_id', sa.Integer(),
            sa.ForeignKey('accounts.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('domain', sa.String(length=255), nullable=True, index=True),
        sa.Column('website', sa.String(length=512), nullable=True),
        sa.Column('industry', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('linkedin_url', sa.String(length=512), nullable=True),
        sa.Column(
            'created_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False, index=True,
        ),
        sa.Column(
            'updated_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )

    op.create_table(
        'company_contacts',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column(
            'company_id', sa.Integer(),
            sa.ForeignKey('companies.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column(
            'contact_id', sa.Integer(),
            sa.ForeignKey('contacts.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column(
            'account_id', sa.Integer(),
            sa.ForeignKey('accounts.id', ondelete='CASCADE'),
            nullable=False, index=True,
        ),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column(
            'added_at', sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint('company_id', 'contact_id', name='uq_company_contact'),
    )


def downgrade() -> None:
    op.drop_table('company_contacts')
    op.drop_table('companies')
