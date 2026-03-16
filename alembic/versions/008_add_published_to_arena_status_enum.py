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
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction in PostgreSQL.
    # Commit the current transaction, then run in autocommit mode.
    conn = op.get_bind()
    conn.execute(text("COMMIT"))
    conn.execution_options(isolation_level="AUTOCOMMIT").execute(
        text("ALTER TYPE arena_status ADD VALUE IF NOT EXISTS 'published'")
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # Downgrade is intentionally a no-op.
    pass
