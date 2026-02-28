"""Add is_active column to languages table

Revision ID: m1n2o3p4q5r6
Revises: g6h7i8j9k0l1
Create Date: 2026-02-26

"""
from alembic import op
import sqlalchemy as sa


revision = "m1n2o3p4q5r6"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add is_active column with default True
    op.add_column(
        "languages",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true"))
    )
    # Add index for performance
    op.create_index(op.f("ix_languages_is_active"), "languages", ["is_active"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_languages_is_active"), table_name="languages")
    op.drop_column("languages", "is_active")
