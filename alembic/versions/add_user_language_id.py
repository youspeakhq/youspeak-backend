"""Add language_id to users table

Revision ID: n2o3p4q5r6s7
Revises: m1n2o3p4q5r6
Create Date: 2026-02-27

"""
from alembic import op
import sqlalchemy as sa


revision = "n2o3p4q5r6s7"
down_revision = "m1n2o3p4q5r6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add language_id column to users table
    op.add_column(
        "users",
        sa.Column("language_id", sa.Integer(), nullable=True)
    )
    # Add foreign key constraint
    op.create_foreign_key(
        "fk_users_language_id",
        "users",
        "languages",
        ["language_id"],
        ["id"],
        ondelete="RESTRICT"
    )
    # Add index for performance
    op.create_index(
        op.f("ix_users_language_id"),
        "users",
        ["language_id"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_users_language_id"), table_name="users")
    op.drop_constraint("fk_users_language_id", "users", type_="foreignkey")
    op.drop_column("users", "language_id")
