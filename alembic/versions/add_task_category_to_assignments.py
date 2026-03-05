"""add task_category to assignments

Revision ID: add_task_category
Revises:
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# revision identifiers, used by Alembic.
revision = 'add_task_category'
down_revision = None  # Update this to point to the actual latest revision
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create the enum type
    task_category_enum = ENUM('assessment', 'assignment', name='task_category', create_type=False)
    task_category_enum.create(op.get_bind(), checkfirst=True)

    # Add the column with default value for existing rows
    op.add_column(
        'assignments',
        sa.Column(
            'category',
            sa.Enum('assessment', 'assignment', name='task_category'),
            nullable=False,
            server_default='assessment'
        )
    )


def downgrade() -> None:
    op.drop_column('assignments', 'category')
    # Optionally drop the enum type
    task_category_enum = ENUM('assessment', 'assignment', name='task_category', create_type=False)
    task_category_enum.drop(op.get_bind(), checkfirst=True)
