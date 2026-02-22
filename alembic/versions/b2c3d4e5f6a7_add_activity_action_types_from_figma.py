"""Add ActivityLog action types from Figma (submission, resource_upload, class_session_completed).

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-22

"""
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'submission'")
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'resource_upload'")
    op.execute("ALTER TYPE activity_action_type ADD VALUE IF NOT EXISTS 'class_session_completed'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; would require recreate type and column.
    pass
