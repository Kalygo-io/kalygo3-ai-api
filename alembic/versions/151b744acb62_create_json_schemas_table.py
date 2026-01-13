"""create_json_schemas_table

Revision ID: 151b744acb62
Revises: ba0f7c242afd
Create Date: 2026-01-13 17:15:10.691050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '151b744acb62'
down_revision: Union[str, None] = 'ba0f7c242afd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the json_schemas table
    op.create_table(
        'json_schemas',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('schema_name', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('schema_definition', postgresql.JSONB, nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create unique constraint on (schema_name, version) to prevent duplicates
    op.create_unique_constraint('uq_json_schemas_name_version', 'json_schemas', ['schema_name', 'version'])
    
    # Create indexes
    op.create_index(op.f('ix_json_schemas_id'), 'json_schemas', ['id'], unique=False)
    op.create_index(op.f('ix_json_schemas_schema_name'), 'json_schemas', ['schema_name'], unique=False)
    op.create_index('ix_json_schemas_name_version', 'json_schemas', ['schema_name', 'version'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_json_schemas_name_version', table_name='json_schemas')
    op.drop_index(op.f('ix_json_schemas_schema_name'), table_name='json_schemas')
    op.drop_index(op.f('ix_json_schemas_id'), table_name='json_schemas')
    
    # Drop unique constraint
    op.drop_constraint('uq_json_schemas_name_version', 'json_schemas', type_='unique')
    
    # Drop table
    op.drop_table('json_schemas')
