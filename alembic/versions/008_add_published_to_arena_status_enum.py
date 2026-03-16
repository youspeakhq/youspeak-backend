"""Add PUBLISHED to arena_status enum

Revision ID: 008_add_published_to_arena_status
Revises: 007_arena_teams
Create Date: 2026-03-16

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '008_add_published_to_arena_status'
down_revision = '007_arena_teams'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a PostgreSQL transaction.
    # We bypass SQLAlchemy's transaction wrapper entirely by using the raw
    # DBAPI connection and setting autocommit at the driver level.
    conn = op.get_bind()
    raw = conn.connection  # raw DBAPI connection (psycopg2)
    original_autocommit = raw.autocommit
    raw.autocommit = True
    try:
        raw.execute("ALTER TYPE arena_status ADD VALUE IF NOT EXISTS 'published'")
    finally:
        raw.autocommit = original_autocommit


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # Downgrade is intentionally a no-op.
    pass
