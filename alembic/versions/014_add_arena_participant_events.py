"""Add arena_participant_events table for speaking/engagement timelines

Revision ID: 014_participant_events
Revises: 013_teacher_rating
Create Date: 2026-04-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = '014_participant_events'
down_revision = '013_teacher_rating'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'arena_participant_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('participant_id', UUID(as_uuid=True), sa.ForeignKey('arena_participants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(30), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('value', sa.Numeric(10, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_arena_participant_events_type', 'arena_participant_events', ['participant_id', 'event_type'])


def downgrade() -> None:
    op.drop_index('ix_arena_participant_events_type', table_name='arena_participant_events')
    op.drop_table('arena_participant_events')
