"""Add ActivityLog action types from Figma (submission, resource_upload, class_session_completed).

Revision ID: d0e1f2a3b4c5
Revises: b2c3d4e5f6a7
Create Date: 2026-02-22

"""
from alembic import op

revision = "d0e1f2a3b4c5"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'submission'")
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'resource_upload'")
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'class_session_completed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; would require recreate type and column.
    pass
