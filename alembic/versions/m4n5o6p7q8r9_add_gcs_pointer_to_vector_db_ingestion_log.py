"""add_gcs_pointer_to_vector_db_ingestion_log

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-06-21

Adds nullable gcs_bucket / gcs_file_path columns to vector_db_ingestion_log so
each ingestion records a pointer back to the original document in Google Cloud
Storage. Nullable for backward compatibility with rows ingested before
per-account GCS storage existed.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'm4n5o6p7q8r9'
down_revision: Union[str, None] = 'l3m4n5o6p7q8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('vector_db_ingestion_log', sa.Column('gcs_bucket', sa.String(), nullable=True))
    op.add_column('vector_db_ingestion_log', sa.Column('gcs_file_path', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('vector_db_ingestion_log', 'gcs_file_path')
    op.drop_column('vector_db_ingestion_log', 'gcs_bucket')
