"""add invited_teacher_id to teacher_access_codes

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
