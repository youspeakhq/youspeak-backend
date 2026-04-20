"""Add teacher_rating and teacher_feedback to arena_participants

Revision ID: 013_teacher_rating
Revises: 012_seed_default_languages
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa


revision = '013_teacher_rating'
down_revision = '012_seed_default_languages'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arena_participants', sa.Column('teacher_rating', sa.Numeric(5, 2), nullable=True))
    op.add_column('arena_participants', sa.Column('teacher_feedback', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('arena_participants', 'teacher_feedback')
    op.drop_column('arena_participants', 'teacher_rating')
