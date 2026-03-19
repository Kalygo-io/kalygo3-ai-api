"""split_contacts_name_into_first_last

Revision ID: l2m3n4o5p6q7
Revises: k1l2m3n4o5p6
Create Date: 2026-03-19

Splits the contacts.name column into first_name (NOT NULL) and last_name (nullable).

Migration strategy for existing rows:
  - The text before the first space becomes first_name.
  - Everything after the first space becomes last_name (NULL if no space).
  - The old name column is then dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'l2m3n4o5p6q7'
down_revision: Union[str, None] = 'k1l2m3n4o5p6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns (nullable initially so existing rows don't violate NOT NULL)
    op.add_column('contacts', sa.Column('first_name', sa.String(length=255), nullable=True))
    op.add_column('contacts', sa.Column('last_name', sa.String(length=255), nullable=True))

    # 2. Populate from existing name column
    #    split_part(name, ' ', 1)  → everything before the first space  (first_name)
    #    NULLIF(split_part(name, ' ', 2), '') → word after first space, or NULL
    #    Note: split_part returns '' (not NULL) when the delimiter isn't found,
    #    so we use NULLIF to convert empty string → NULL for last_name.
    op.execute("""
        UPDATE contacts
        SET
            first_name = split_part(name, ' ', 1),
            last_name  = NULLIF(
                            substring(name FROM position(' ' IN name) + 1),
                            ''
                         )
        WHERE name IS NOT NULL
    """)

    # 3. Set first_name NOT NULL now that all rows are populated
    op.alter_column('contacts', 'first_name', nullable=False)

    # 4. Drop the old name column
    op.drop_column('contacts', 'name')

    # 5. Add indexes on the new columns
    op.create_index('ix_contacts_first_name', 'contacts', ['first_name'])


def downgrade() -> None:
    # Reverse: re-add name, populate from first_name + last_name, drop new columns
    op.add_column('contacts', sa.Column('name', sa.String(length=255), nullable=True))

    op.execute("""
        UPDATE contacts
        SET name = CASE
            WHEN last_name IS NOT NULL AND last_name <> ''
                THEN first_name || ' ' || last_name
            ELSE first_name
        END
    """)

    op.alter_column('contacts', 'name', nullable=False)
    op.drop_index('ix_contacts_first_name', table_name='contacts')
    op.drop_column('contacts', 'last_name')
    op.drop_column('contacts', 'first_name')
