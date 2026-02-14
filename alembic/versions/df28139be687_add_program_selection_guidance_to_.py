"""add_program_selection_guidance_to_inquiry_type

Revision ID: df28139be687
Revises: da830fe3b4f8
Create Date: 2026-02-14 14:26:03.820379

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df28139be687'
down_revision = 'da830fe3b4f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE inquiry_type ADD VALUE IF NOT EXISTS 'PROGRAM_SELECTION_GUIDANCE'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values
