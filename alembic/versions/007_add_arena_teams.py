"""007_add_arena_teams

Create arena_teams and arena_team_members tables for collaborative mode.

Revision ID: 007_add_arena_teams
Revises: 006_add_challenge_pool_fields
Create Date: 2026-03-16 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '007_add_arena_teams'
down_revision: Union[str, None] = '006_add_challenge_pool_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create arena_teams table
    op.create_table(
        'arena_teams',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('arena_id', UUID(as_uuid=True), sa.ForeignKey('arenas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_name', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('arena_id', 'team_name', name='uq_arena_teams_arena_team_name'),
    )

    # Index for arena queries
    op.create_index('idx_arena_teams_arena', 'arena_teams', ['arena_id'])

    # 2. Create arena_team_members table
    op.create_table(
        'arena_team_members',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('team_id', UUID(as_uuid=True), sa.ForeignKey('arena_teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), server_default='member', nullable=False),  # 'leader' | 'member'
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.UniqueConstraint('team_id', 'student_id', name='uq_team_members_team_student'),
    )

    # Indexes for efficient queries
    op.create_index('idx_team_members_team', 'arena_team_members', ['team_id'])
    op.create_index('idx_team_members_student', 'arena_team_members', ['student_id'])


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_team_members_student', table_name='arena_team_members')
    op.drop_index('idx_team_members_team', table_name='arena_team_members')
    op.drop_index('idx_arena_teams_arena', table_name='arena_teams')

    # Drop tables (CASCADE will handle foreign keys)
    op.drop_table('arena_team_members')
    op.drop_table('arena_teams')
