"""Add student_number to users for human-readable student IDs

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-02-16

Format: {year}-{seq} e.g. 2025-001. Unique per school.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("student_number", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_users_school_student_number",
        "users",
        ["school_id", "student_number"],
        unique=True,
        postgresql_where=sa.text("student_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_school_student_number", table_name="users")
    op.drop_column("users", "student_number")
