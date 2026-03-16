"""Add arena_participants and arena_reactions tables

Revision ID: 005_participants_reactions
Revises: 004_add_timestamps
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '005_participants_reactions'
down_revision = '004_add_timestamps'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create arena_participants table
    op.create_table(
        'arena_participants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('arena_id', UUID(as_uuid=True), sa.ForeignKey('arenas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='participant'),  # 'participant' | 'audience'
        sa.Column('team_id', UUID(as_uuid=True), nullable=True),  # For Phase 6 collaborative mode
        sa.Column('is_speaking', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('speaking_start_time', sa.DateTime(), nullable=True),
        sa.Column('total_speaking_duration_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('engagement_score', sa.Numeric(5, 2), nullable=False, server_default='0.00'),  # 0.00 to 100.00
        sa.Column('last_activity', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('arena_id', 'student_id', name='uq_arena_student_participant')
    )

    # Create indexes for arena_participants
    op.create_index('idx_participants_arena', 'arena_participants', ['arena_id'])
    op.create_index('idx_participants_speaking', 'arena_participants', ['arena_id', 'is_speaking'])
    op.create_index('idx_participants_team', 'arena_participants', ['team_id'])

    # Create arena_reactions table
    op.create_table(
        'arena_reactions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('arena_id', UUID(as_uuid=True), sa.ForeignKey('arenas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_participant_id', UUID(as_uuid=True), sa.ForeignKey('arena_participants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('reaction_type', sa.String(20), nullable=False),  # 'heart' | 'clap' | 'laugh' | 'thumbs_up'
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )

    # Create indexes for arena_reactions
    op.create_index('idx_reactions_arena', 'arena_reactions', ['arena_id', 'reaction_type'])
    op.create_index('idx_reactions_participant', 'arena_reactions', ['target_participant_id'])
    op.create_index('idx_reactions_timestamp', 'arena_reactions', ['arena_id', 'timestamp'], postgresql_using='btree', postgresql_ops={'timestamp': 'DESC'})


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_reactions_timestamp', table_name='arena_reactions')
    op.drop_index('idx_reactions_participant', table_name='arena_reactions')
    op.drop_index('idx_reactions_arena', table_name='arena_reactions')

    # Drop arena_reactions table
    op.drop_table('arena_reactions')

    # Drop indexes
    op.drop_index('idx_participants_team', table_name='arena_participants')
    op.drop_index('idx_participants_speaking', table_name='arena_participants')
    op.drop_index('idx_participants_arena', table_name='arena_participants')

    # Drop arena_participants table
    op.drop_table('arena_participants')
