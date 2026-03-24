"""add_email_logs_table

Revision ID: f48298ca174c
Revises: 009_add_published_enum
Create Date: 2026-03-24 16:46:58.771585

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'f48298ca174c'
down_revision = '009_add_published_enum'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum reference (for use in table definition)
    email_send_status = postgresql.ENUM('PENDING', 'SENT', 'FAILED', name='email_send_status', create_type=False)

    # Create email_send_status enum if it doesn't exist
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'email_send_status'"
    ))
    if not result.fetchone():
        email_send_status.create(conn, checkfirst=True)

    # Create email_logs table
    op.create_table(
        'email_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('recipients', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('subject', sa.Text(), nullable=False),
        sa.Column('html_body_sha256', sa.String(64), nullable=False),
        sa.Column('send_status', email_send_status, nullable=False, server_default='PENDING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    )

    # Create indexes
    op.create_index('ix_email_logs_school_id', 'email_logs', ['school_id'])
    op.create_index('ix_email_logs_sender_id', 'email_logs', ['sender_id'])
    op.create_index('ix_email_logs_send_status', 'email_logs', ['send_status'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_email_logs_send_status', table_name='email_logs')
    op.drop_index('ix_email_logs_sender_id', table_name='email_logs')
    op.drop_index('ix_email_logs_school_id', table_name='email_logs')

    # Drop table
    op.drop_table('email_logs')

    # Drop enum if it exists
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'email_send_status'"
    ))
    if result.fetchone():
        email_send_status = postgresql.ENUM('PENDING', 'SENT', 'FAILED', name='email_send_status', create_type=False)
        email_send_status.drop(conn, checkfirst=True)
