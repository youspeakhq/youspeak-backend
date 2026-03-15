"""Add arena session configuration fields

Revision ID: 001_arena_session_config
Revises:
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_arena_session_config'
down_revision = None  # Update this to previous migration ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add session configuration columns to arenas table
    op.add_column('arenas', sa.Column('arena_mode', sa.String(20), nullable=True))
    op.add_column('arenas', sa.Column('judging_mode', sa.String(20), nullable=True))
    op.add_column('arenas', sa.Column('ai_co_judge_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('arenas', sa.Column('student_selection_mode', sa.String(20), nullable=True))
    op.add_column('arenas', sa.Column('session_state', sa.String(20), nullable=False, server_default='not_started'))
    op.add_column('arenas', sa.Column('team_size', sa.Integer(), nullable=True))

    # Add index on session_state for querying
    op.create_index('idx_arenas_session_state', 'arenas', ['session_state'])


def downgrade() -> None:
    # Remove index
    op.drop_index('idx_arenas_session_state', table_name='arenas')

    # Remove columns
    op.drop_column('arenas', 'team_size')
    op.drop_column('arenas', 'session_state')
    op.drop_column('arenas', 'student_selection_mode')
    op.drop_column('arenas', 'ai_co_judge_enabled')
    op.drop_column('arenas', 'judging_mode')
    op.drop_column('arenas', 'arena_mode')
