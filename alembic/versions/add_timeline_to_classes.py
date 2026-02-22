"""add timeline to classes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    has_timeline = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'classes' AND column_name = 'timeline'"
            )
        ).scalar()
        is not None
    )
    if not has_timeline:
        op.add_column("classes", sa.Column("timeline", sa.String(100), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    has_timeline = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'classes' AND column_name = 'timeline'"
            )
        ).scalar()
        is not None
    )
    if has_timeline:
        op.drop_column("classes", "timeline")
