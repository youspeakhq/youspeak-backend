"""Ensure users.language_id exists (idempotent)

Revision ID: e7f8a9b0c1d2
Revises: c183112ada28
Create Date: 2026-02-28

Run after merge so DBs that applied only one branch still get the column.
Uses PostgreSQL IF NOT EXISTS so safe to run multiple times.
"""
from alembic import op


revision = "e7f8a9b0c1d2"
down_revision = "c183112ada28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add column if missing (idempotent at DB level; avoids reliance on migration order)
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS language_id INTEGER REFERENCES languages(id) ON DELETE RESTRICT"
    )
    # Index if not exists (PostgreSQL 9.5+)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_language_id ON users (language_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_language_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_language_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_language_id_fkey")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS language_id")
