"""Ensure schema consistency: lowercase enums, timeline column

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-02-16

Idempotent migration for DBs that may have been stamped without running
add_lowercase or add_timeline. Safe to run multiple times.
"""
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lowercase enum values (PostgreSQL ADD VALUE IF NOT EXISTS)
    for value in ("billing", "demo_request", "new_onboarding", "program_selection_guidance"):
        op.execute(f"ALTER TYPE inquiry_type ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("primary", "secondary", "tertiary"):
        op.execute(f"ALTER TYPE school_type ADD VALUE IF NOT EXISTS '{value}'")
    for value in ("pioneer", "partnership"):
        op.execute(f"ALTER TYPE program_type ADD VALUE IF NOT EXISTS '{value}'")

    # Timeline column on classes (PostgreSQL 9.6+)
    op.execute(
        "ALTER TABLE classes ADD COLUMN IF NOT EXISTS timeline VARCHAR(100)"
    )


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values; column drop is destructive
