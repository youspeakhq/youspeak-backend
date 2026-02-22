"""add invited_teacher_id to teacher_access_codes

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    has_col = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'teacher_access_codes' AND column_name = 'invited_teacher_id'"
            )
        ).scalar()
        is not None
    )
    if not has_col:
        op.add_column(
            "teacher_access_codes",
            sa.Column("invited_teacher_id", sa.UUID(), nullable=True),
        )
        op.create_foreign_key(
            "fk_teacher_access_codes_invited_teacher_id",
            "teacher_access_codes",
            "users",
            ["invited_teacher_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(
            op.f("ix_teacher_access_codes_invited_teacher_id"),
            "teacher_access_codes",
            ["invited_teacher_id"],
            unique=False,
        )


def downgrade() -> None:
    conn = op.get_bind()
    has_col = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'teacher_access_codes' AND column_name = 'invited_teacher_id'"
            )
        ).scalar()
        is not None
    )
    if has_col:
        op.drop_index(
            op.f("ix_teacher_access_codes_invited_teacher_id"),
            table_name="teacher_access_codes",
        )
        op.drop_constraint(
            "fk_teacher_access_codes_invited_teacher_id",
            "teacher_access_codes",
            type_="foreignkey",
        )
        op.drop_column("teacher_access_codes", "invited_teacher_id")
