"""Add PUBLISHED to arena_status enum

Revision ID: 008
Revises: 007_add_arena_teams
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '008_add_published_to_arena_status'
down_revision = '007_add_arena_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL requires ALTER TYPE to add new enum values
    # This is done outside a transaction for enum alterations on PostgreSQL
    op.execute("ALTER TYPE arena_status ADD VALUE IF NOT EXISTS 'published'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values easily.
    # To downgrade, we would need to create a new type and swap columns.
    # For safety, this is a no-op downgrade.
    pass
