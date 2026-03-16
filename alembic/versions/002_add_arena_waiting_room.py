"""Add arena waiting room table

Revision ID: 002_arena_waiting_room
Revises: 001_arena_session_config
Create Date: 2026-03-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '002_arena_waiting_room'
down_revision = '001_arena_session_config'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add join code fields to arenas table
    op.add_column('arenas', sa.Column('join_code', sa.String(20), nullable=True))
    op.add_column('arenas', sa.Column('qr_code_url', sa.Text(), nullable=True))
    op.add_column('arenas', sa.Column('join_code_expires_at', sa.DateTime(), nullable=True))

    # Add unique index on join_code (for active codes only)
    op.create_index('idx_arenas_join_code', 'arenas', ['join_code'],
                    unique=True,
                    postgresql_where=sa.text('join_code IS NOT NULL'))

    # Create arena_waiting_room table
    op.create_table(
        'arena_waiting_room',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('arena_id', UUID(as_uuid=True), sa.ForeignKey('arenas.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('student_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('entry_timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # 'pending' | 'admitted' | 'rejected'
        sa.Column('admitted_at', sa.DateTime(), nullable=True),
        sa.Column('admitted_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('arena_id', 'student_id', name='uq_arena_student_waiting_room')
    )

    # Create indexes
    op.create_index('idx_waiting_room_arena_status', 'arena_waiting_room', ['arena_id', 'status'])
    op.create_index('idx_waiting_room_student', 'arena_waiting_room', ['student_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_waiting_room_student', table_name='arena_waiting_room')
    op.drop_index('idx_waiting_room_arena_status', table_name='arena_waiting_room')

    # Drop table
    op.drop_table('arena_waiting_room')

    # Remove index from arenas
    op.drop_index('idx_arenas_join_code', table_name='arenas')

    # Remove columns from arenas
    op.drop_column('arenas', 'join_code_expires_at')
    op.drop_column('arenas', 'qr_code_url')
    op.drop_column('arenas', 'join_code')
