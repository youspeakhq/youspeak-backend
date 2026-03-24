"""add_arena_recording_fields

Revision ID: g52409db286d
Revises: f48298ca174c
Create Date: 2026-03-24 17:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g52409db286d'
down_revision = 'f48298ca174c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add Cloudflare RealtimeKit audio conferencing fields to arenas table
    op.add_column('arenas', sa.Column('realtimekit_meeting_id', sa.String(255), nullable=True))
    op.add_column('arenas', sa.Column('recording_started_at', sa.DateTime(), nullable=True))
    op.add_column('arenas', sa.Column('recording_stopped_at', sa.DateTime(), nullable=True))
    op.add_column('arenas', sa.Column('recording_url', sa.Text(), nullable=True))
    op.add_column('arenas', sa.Column('recording_status', sa.String(20), nullable=False, server_default='not_started'))
    op.add_column('arenas', sa.Column('transcription_status', sa.String(20), nullable=False, server_default='not_started'))
    op.add_column('arenas', sa.Column('transcription_url', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove RealtimeKit fields from arenas table
    op.drop_column('arenas', 'transcription_url')
    op.drop_column('arenas', 'transcription_status')
    op.drop_column('arenas', 'recording_status')
    op.drop_column('arenas', 'recording_url')
    op.drop_column('arenas', 'recording_stopped_at')
    op.drop_column('arenas', 'recording_started_at')
    op.drop_column('arenas', 'realtimekit_meeting_id')
