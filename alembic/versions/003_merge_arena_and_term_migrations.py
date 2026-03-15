"""Merge arena and term migrations

Revision ID: 003_merge_heads
Revises: 002_arena_waiting_room, 2bf135a002d9
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003_merge_heads'
down_revision = ('002_arena_waiting_room', '2bf135a002d9')
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Merge migration - no changes needed
    pass


def downgrade() -> None:
    # Merge migration - no changes needed
    pass
