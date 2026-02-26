"""Add lowercase enum values for Python enum compatibility

Revision ID: a0b1c2d3e4f5
Revises: df28139be687
Create Date: 2026-02-08

PostgreSQL enums use uppercase. Python enums use lowercase values.
Add lowercase values so inserts from the API work.
"""
from alembic import op


revision = "a0b1c2d3e4f5"
down_revision = "df28139be687"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for value in ("billing", "demo_request", "new_onboarding", "program_selection_guidance"):
        op.execute(f"ALTER TYPE inquiry_type ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("primary", "secondary", "mixed"):
        op.execute(f"ALTER TYPE school_type ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("pioneer", "partnership"):
        op.execute(f"ALTER TYPE program_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values
