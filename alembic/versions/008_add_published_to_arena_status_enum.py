"""Add PUBLISHED to arena_status enum

Revision ID: 008_add_published_to_arena_status
Revises: 007_arena_teams
Create Date: 2026-03-16

"""
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = '008_add_published_to_arena_status'
down_revision = '007_arena_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL 12+ allows ALTER TYPE ADD VALUE inside a transaction when
    # using IF NOT EXISTS. asyncpg handles this correctly.
    op.execute(text("ALTER TYPE arena_status ADD VALUE IF NOT EXISTS 'published'"))


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # Downgrade is intentionally a no-op.
    pass
