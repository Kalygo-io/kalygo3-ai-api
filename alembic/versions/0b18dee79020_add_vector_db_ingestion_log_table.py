"""add_vector_db_ingestion_log_table

Revision ID: 0b18dee79020
Revises: 166bbf223e15
Create Date: 2025-12-14 04:19:25.626536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0b18dee79020'
down_revision: Union[str, None] = '166bbf223e15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    operation_type_enum = postgresql.ENUM(
        'INGEST',
        'DELETE',
        'UPDATE',
        name='operation_type_enum',
        create_type=True
    )
    operation_type_enum.create(op.get_bind(), checkfirst=True)
    
    operation_status_enum = postgresql.ENUM(
        'SUCCESS',
        'FAILED',
        'PARTIAL',
        'PENDING',
        name='operation_status_enum',
        create_type=True
    )
    operation_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create the vector_db_ingestion_log table (initially with String columns)
    op.create_table(
        'vector_db_ingestion_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('operation_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('index_name', sa.String(), nullable=False),
        sa.Column('namespace', sa.String(), nullable=True),
        sa.Column('filenames', postgresql.JSON, nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('vectors_added', sa.Integer(), server_default='0', nullable=False),
        sa.Column('vectors_deleted', sa.Integer(), server_default='0', nullable=False),
        sa.Column('vectors_failed', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(), nullable=True),
        sa.Column('batch_number', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ),
    )
    
    # Create indexes
    op.create_index(op.f('ix_vector_db_ingestion_log_id'), 'vector_db_ingestion_log', ['id'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_created_at'), 'vector_db_ingestion_log', ['created_at'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_operation_type'), 'vector_db_ingestion_log', ['operation_type'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_status'), 'vector_db_ingestion_log', ['status'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_account_id'), 'vector_db_ingestion_log', ['account_id'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_index_name'), 'vector_db_ingestion_log', ['index_name'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_namespace'), 'vector_db_ingestion_log', ['namespace'], unique=False)
    op.create_index(op.f('ix_vector_db_ingestion_log_batch_number'), 'vector_db_ingestion_log', ['batch_number'], unique=False)
    
    # Create composite index for common queries
    op.create_index('ix_vector_db_log_account_index', 'vector_db_ingestion_log', ['account_id', 'index_name'], unique=False)
    
    # Convert String columns to enum types
    op.execute("""
        ALTER TABLE vector_db_ingestion_log 
        ALTER COLUMN operation_type TYPE operation_type_enum 
        USING operation_type::operation_type_enum
    """)
    
    op.execute("""
        ALTER TABLE vector_db_ingestion_log 
        ALTER COLUMN status TYPE operation_status_enum 
        USING status::operation_status_enum
    """)


def downgrade() -> None:
    # Convert enum columns back to String before dropping
    op.execute("""
        ALTER TABLE vector_db_ingestion_log 
        ALTER COLUMN operation_type TYPE VARCHAR 
        USING operation_type::VARCHAR
    """)
    
    op.execute("""
        ALTER TABLE vector_db_ingestion_log 
        ALTER COLUMN status TYPE VARCHAR 
        USING status::VARCHAR
    """)
    
    # Drop indexes
    op.drop_index('ix_vector_db_log_account_index', table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_batch_number'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_namespace'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_index_name'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_account_id'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_status'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_operation_type'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_created_at'), table_name='vector_db_ingestion_log')
    op.drop_index(op.f('ix_vector_db_ingestion_log_id'), table_name='vector_db_ingestion_log')
    
    # Drop table
    op.drop_table('vector_db_ingestion_log')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS operation_status_enum")
    op.execute("DROP TYPE IF EXISTS operation_type_enum")
