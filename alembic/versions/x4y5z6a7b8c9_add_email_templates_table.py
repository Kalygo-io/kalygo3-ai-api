"""add_email_templates_table

Revision ID: x4y5z6a7b8c9
Revises: w3x4y5z6a7b8
Create Date: 2026-04-04

Adds email_templates — a library of reusable, production-grade HTML email
templates with named variable slots.  The send_template_email_with_ses agent
tool renders a template at invocation time, replacing {{variable}} tokens,
then queues the rendered HTML for human approval before sending via SES.
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = 'x4y5z6a7b8c9'
down_revision: Union[str, None] = 'w3x4y5z6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(),
                  sa.ForeignKey('accounts.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        # Subject may also contain {{variable}} tokens
        sa.Column('subject_template', sa.String(998), nullable=False),
        # Full HTML — must be inbox-compatible (inline CSS, table layout, ≤600 px)
        sa.Column('html_template', sa.Text(), nullable=False),
        # JSON array of variable descriptors:
        # [{"name": "first_name", "label": "First Name", "default": "there"}]
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_email_templates_id', 'email_templates', ['id'])
    op.create_index('ix_email_templates_account_id', 'email_templates', ['account_id'])
    op.create_index('ix_email_templates_name', 'email_templates', ['account_id', 'name'])


def downgrade() -> None:
    op.drop_index('ix_email_templates_name', 'email_templates')
    op.drop_index('ix_email_templates_account_id', 'email_templates')
    op.drop_index('ix_email_templates_id', 'email_templates')
    op.drop_table('email_templates')
