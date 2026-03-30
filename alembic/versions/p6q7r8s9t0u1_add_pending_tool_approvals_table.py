"""add pending_tool_approvals table

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'p6q7r8s9t0u1'
down_revision = 'o5p6q7r8s9t0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'pending_tool_approvals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('chat_session_id', sa.Integer(), nullable=True),
        sa.Column('tool_type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['chat_session_id'], ['chat_sessions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pending_tool_approvals_id', 'pending_tool_approvals', ['id'])
    op.create_index('ix_pending_tool_approvals_account_id', 'pending_tool_approvals', ['account_id'])
    op.create_index('ix_pending_tool_approvals_agent_id', 'pending_tool_approvals', ['agent_id'])
    op.create_index('ix_pending_tool_approvals_chat_session_id', 'pending_tool_approvals', ['chat_session_id'])
    op.create_index('ix_pending_tool_approvals_tool_type', 'pending_tool_approvals', ['tool_type'])
    op.create_index('ix_pending_tool_approvals_status', 'pending_tool_approvals', ['status'])


def downgrade() -> None:
    op.drop_index('ix_pending_tool_approvals_status', table_name='pending_tool_approvals')
    op.drop_index('ix_pending_tool_approvals_tool_type', table_name='pending_tool_approvals')
    op.drop_index('ix_pending_tool_approvals_chat_session_id', table_name='pending_tool_approvals')
    op.drop_index('ix_pending_tool_approvals_agent_id', table_name='pending_tool_approvals')
    op.drop_index('ix_pending_tool_approvals_account_id', table_name='pending_tool_approvals')
    op.drop_index('ix_pending_tool_approvals_id', table_name='pending_tool_approvals')
    op.drop_table('pending_tool_approvals')
