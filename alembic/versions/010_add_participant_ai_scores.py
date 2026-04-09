"""Add AI pronunciation and fluency score columns to arena_participants

Revision ID: 010_ai_scores
Revises: g52409db286d
Create Date: 2026-04-09

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_ai_scores'
down_revision = 'g52409db286d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'arena_participants',
        sa.Column('ai_pronunciation_score', sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        'arena_participants',
        sa.Column('ai_fluency_score', sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('arena_participants', 'ai_fluency_score')
    op.drop_column('arena_participants', 'ai_pronunciation_score')
