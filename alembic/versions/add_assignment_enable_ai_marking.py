"""Add enable_ai_marking to assignments

Revision ID: add_ai_marking
Revises: a1b2c3d4e5f6
Create Date: 2026-02-25

"""
from alembic import op
import sqlalchemy as sa


revision = "add_ai_marking"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "assignments",
        sa.Column("enable_ai_marking", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("assignments", "enable_ai_marking")
