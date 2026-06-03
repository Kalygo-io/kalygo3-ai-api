"""add_social_profiles_to_contacts

Revision ID: g6h7i8j9k0l1
Revises: f5g6h7i8j9k0
Create Date: 2026-06-02

Adds optional social media profile URL columns to the contacts table:
LinkedIn, Instagram, YouTube, and X (formerly Twitter).

Stored as full profile URLs, one nullable column per platform — consistent
with the existing flat one-per-contact columns (phone, alternate emails).
All nullable so existing rows are unaffected.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'g6h7i8j9k0l1'
down_revision: Union[str, None] = 'f5g6h7i8j9k0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('linkedin_url', sa.String(length=512), nullable=True))
    op.add_column('contacts', sa.Column('instagram_url', sa.String(length=512), nullable=True))
    op.add_column('contacts', sa.Column('youtube_url', sa.String(length=512), nullable=True))
    op.add_column('contacts', sa.Column('x_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'x_url')
    op.drop_column('contacts', 'youtube_url')
    op.drop_column('contacts', 'instagram_url')
    op.drop_column('contacts', 'linkedin_url')
