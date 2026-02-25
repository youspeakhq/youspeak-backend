"""Add email and phone to schools (Figma Bio Data)

Revision ID: a1b2c3d4e5f7
Revises: f6a7b8c9d0e1
Create Date: 2026-02-25

School Information / Bio Data: School Name, School Type, School Email.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "a1b2c3d4e5f7"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    for col in ("email", "phone"):
        has_col = (
            conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'schools' AND column_name = :name"
                ),
                {"name": col},
            ).scalar()
            is not None
        )
        if not has_col:
            length = 255 if col == "email" else 50
            op.add_column(
                "schools",
                sa.Column(col, sa.String(length=length), nullable=True),
            )


def downgrade() -> None:
    conn = op.get_bind()
    for col in ("phone", "email"):
        has_col = (
            conn.execute(
                text(
                    "SELECT 1 FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'schools' AND column_name = :name"
                ),
                {"name": col},
            ).scalar()
            is not None
        )
        if has_col:
            op.drop_column("schools", col)
