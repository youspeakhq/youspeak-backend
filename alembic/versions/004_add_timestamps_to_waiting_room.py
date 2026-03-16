"""Add created_at and updated_at to arena_waiting_room

Revision ID: 004_add_timestamps
Revises: 003_merge_heads
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_add_timestamps'
down_revision = '003_merge_heads'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add created_at and updated_at columns to arena_waiting_room
    # These were missing from the original migration but are part of BaseModel
    op.execute("""
        ALTER TABLE arena_waiting_room
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    """)

    op.execute("""
        ALTER TABLE arena_waiting_room
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    """)


def downgrade() -> None:
    # Remove the timestamp columns
    op.drop_column('arena_waiting_room', 'updated_at')
    op.drop_column('arena_waiting_room', 'created_at')
