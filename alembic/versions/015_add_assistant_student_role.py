"""add assistant to student_role enum

Revision ID: 015_add_assistant_student_role
Revises: 014_participant_events
Create Date: 2026-04-23
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "015_add_assistant_student_role"
down_revision = "014_participant_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE student_role ADD VALUE IF NOT EXISTS 'ASSISTANT'")


def downgrade() -> None:
    # PostgreSQL enum value removal is not safe in-place.
    pass
