"""Rename chat_app_sessions to chat_sessions and replace chat_app_id with agent_id

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-27 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Rename chat_app_sessions table to chat_sessions
    op.rename_table('chat_app_sessions', 'chat_sessions')
    
    # Step 2: Rename chat_app_messages table to chat_messages
    op.rename_table('chat_app_messages', 'chat_messages')
    
    # Step 3: Add agent_id column (nullable initially for migration)
    op.add_column('chat_sessions', sa.Column('agent_id', sa.Integer(), nullable=True))
    
    # Step 4: Create foreign key for agent_id
    op.create_foreign_key(
        'chat_sessions_agent_id_fkey',
        'chat_sessions',
        'agents',
        ['agent_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Step 5: Create index on agent_id
    op.create_index('ix_chat_sessions_agent_id', 'chat_sessions', ['agent_id'])
    
    # Step 6: Migrate existing data - extract agent_id from chat_app_id where possible
    # chat_app_id was stored as 'agent-{id}' format
    op.execute("""
        UPDATE chat_sessions 
        SET agent_id = CAST(SUBSTRING(chat_app_id FROM 'agent-([0-9]+)') AS INTEGER)
        WHERE chat_app_id LIKE 'agent-%'
        AND SUBSTRING(chat_app_id FROM 'agent-([0-9]+)') IS NOT NULL
    """)
    
    # Step 7: Drop the old chat_app_id column
    op.drop_index('ix_chat_app_sessions_chat_app_id', table_name='chat_sessions')
    op.drop_column('chat_sessions', 'chat_app_id')
    
    # Step 8: Rename the foreign key column in chat_messages
    op.alter_column('chat_messages', 'chat_app_session_id', new_column_name='chat_session_id')
    
    # Step 9: Update the foreign key constraint on chat_messages
    # First drop the old constraint
    op.drop_constraint('chat_app_messages_chat_app_session_id_fkey', 'chat_messages', type_='foreignkey')
    
    # Create new constraint with updated names
    op.create_foreign_key(
        'chat_messages_chat_session_id_fkey',
        'chat_messages',
        'chat_sessions',
        ['chat_session_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Step 10: Rename indexes on chat_sessions
    op.drop_index('ix_chat_app_sessions_account_id', table_name='chat_sessions')
    op.drop_index('ix_chat_app_sessions_session_id', table_name='chat_sessions')
    op.create_index('ix_chat_sessions_account_id', 'chat_sessions', ['account_id'])
    op.create_index('ix_chat_sessions_session_id', 'chat_sessions', ['session_id'], unique=True)
    
    # Step 11: Rename index on chat_messages
    op.drop_index('ix_chat_app_messages_chat_app_session_id', table_name='chat_messages')
    op.create_index('ix_chat_messages_chat_session_id', 'chat_messages', ['chat_session_id'])
    
    # Step 12: Update primary key constraint names (PostgreSQL specific)
    op.execute('ALTER TABLE chat_sessions RENAME CONSTRAINT chat_app_sessions_pkey TO chat_sessions_pkey')
    op.execute('ALTER TABLE chat_messages RENAME CONSTRAINT chat_app_messages_pkey TO chat_messages_pkey')
    
    # Step 13: Update account foreign key constraint name
    op.drop_constraint('chat_app_sessions_account_id_fkey', 'chat_sessions', type_='foreignkey')
    op.create_foreign_key(
        'chat_sessions_account_id_fkey',
        'chat_sessions',
        'accounts',
        ['account_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade() -> None:
    # Reverse the migration
    
    # Re-add chat_app_id column
    op.add_column('chat_sessions', sa.Column('chat_app_id', sa.String(), nullable=True))
    op.create_index('ix_chat_app_sessions_chat_app_id', 'chat_sessions', ['chat_app_id'])
    
    # Migrate data back
    op.execute("""
        UPDATE chat_sessions 
        SET chat_app_id = 'agent-' || agent_id::text
        WHERE agent_id IS NOT NULL
    """)
    
    # Drop agent_id foreign key and column
    op.drop_constraint('chat_sessions_agent_id_fkey', 'chat_sessions', type_='foreignkey')
    op.drop_index('ix_chat_sessions_agent_id', table_name='chat_sessions')
    op.drop_column('chat_sessions', 'agent_id')
    
    # Rename column in chat_messages back
    op.drop_constraint('chat_messages_chat_session_id_fkey', 'chat_messages', type_='foreignkey')
    op.alter_column('chat_messages', 'chat_session_id', new_column_name='chat_app_session_id')
    op.create_foreign_key(
        'chat_app_messages_chat_app_session_id_fkey',
        'chat_messages',
        'chat_sessions',
        ['chat_app_session_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Rename indexes back
    op.drop_index('ix_chat_sessions_account_id', table_name='chat_sessions')
    op.drop_index('ix_chat_sessions_session_id', table_name='chat_sessions')
    op.create_index('ix_chat_app_sessions_account_id', 'chat_sessions', ['account_id'])
    op.create_index('ix_chat_app_sessions_session_id', 'chat_sessions', ['session_id'], unique=True)
    
    op.drop_index('ix_chat_messages_chat_session_id', table_name='chat_messages')
    op.create_index('ix_chat_app_messages_chat_app_session_id', 'chat_messages', ['chat_app_session_id'])
    
    # Rename primary key constraints back
    op.execute('ALTER TABLE chat_sessions RENAME CONSTRAINT chat_sessions_pkey TO chat_app_sessions_pkey')
    op.execute('ALTER TABLE chat_messages RENAME CONSTRAINT chat_messages_pkey TO chat_app_messages_pkey')
    
    # Update account foreign key constraint name back
    op.drop_constraint('chat_sessions_account_id_fkey', 'chat_sessions', type_='foreignkey')
    op.create_foreign_key(
        'chat_app_sessions_account_id_fkey',
        'chat_sessions',
        'accounts',
        ['account_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Rename tables back
    op.rename_table('chat_messages', 'chat_app_messages')
    op.rename_table('chat_sessions', 'chat_app_sessions')
