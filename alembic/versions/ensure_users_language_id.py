"""Ensure users.language_id exists (idempotent)

Revision ID: e7f8a9b0c1d2
Revises: c183112ada28
Create Date: 2026-02-28

Run after merge so DBs that applied only one branch still get the column.
Safe to run multiple times.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "e7f8a9b0c1d2"
down_revision = "c183112ada28"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    has_col = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'language_id'"
            )
        ).scalar()
        is not None
    )
    if not has_col:
        op.add_column(
            "users",
            sa.Column("language_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_users_language_id",
            "users",
            "languages",
            ["language_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            op.f("ix_users_language_id"),
            "users",
            ["language_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    has_col = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'language_id'"
            )
        ).scalar()
        is not None
    )
    if has_col:
        op.drop_index(op.f("ix_users_language_id"), table_name="users")
        op.drop_constraint("fk_users_language_id", "users", type_="foreignkey")
        op.drop_column("users", "language_id")
