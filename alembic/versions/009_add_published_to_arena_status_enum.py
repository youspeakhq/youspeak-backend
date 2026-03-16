"""add PUBLISHED to arena_status enum for existing dbs

Revision ID: 009_add_published_to_arena_status_enum
Revises: 007_arena_teams
Create Date: 2026-03-16 23:25:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '009_add_published_to_arena_status_enum'
down_revision = '007_arena_teams'
branch_labels = None
depends_on = None


def upgrade():
    # Use op.get_bind() to execute the ALTER TYPE command.
    # We must use IF NOT EXISTS since fresh DBs already have this value 
    # from the initial schema patch I made earlier.
    conn = op.get_bind()
    conn.execute(text("ALTER TYPE arena_status ADD VALUE IF NOT EXISTS 'PUBLISHED'"))


def downgrade():
    # PostgreSQL doesn't support removing values from an enum easily.
    pass
