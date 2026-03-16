"""Add challenge pool fields to arenas

Revision ID: 006_challenge_pool
Revises: 005_participants_reactions
Create Date: 2026-03-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = '006_challenge_pool'
down_revision = '005_participants_reactions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add challenge pool fields to arenas table
    op.add_column('arenas', sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('arenas', sa.Column('source_pool_challenge_id', UUID(as_uuid=True), nullable=True))
    op.add_column('arenas', sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('arenas', sa.Column('published_at', sa.DateTime(), nullable=True))
    op.add_column('arenas', sa.Column('published_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # Create indexes for pool queries
    op.create_index('idx_arenas_is_public', 'arenas', ['is_public', 'status'])
    op.create_index('idx_arenas_usage_count', 'arenas', ['usage_count'], postgresql_using='btree', postgresql_ops={'usage_count': 'DESC'})
    op.create_index('idx_arenas_published_at', 'arenas', ['published_at'], postgresql_using='btree', postgresql_ops={'published_at': 'DESC'})

    # Create foreign key for source_pool_challenge_id (self-referencing)
    op.create_foreign_key(
        'fk_arenas_source_pool',
        'arenas',
        'arenas',
        ['source_pool_challenge_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_arenas_published_at', table_name='arenas')
    op.drop_index('idx_arenas_usage_count', table_name='arenas')
    op.drop_index('idx_arenas_is_public', table_name='arenas')

    # Drop foreign key
    op.drop_constraint('fk_arenas_source_pool', 'arenas', type_='foreignkey')

    # Drop columns
    op.drop_column('arenas', 'published_by')
    op.drop_column('arenas', 'published_at')
    op.drop_column('arenas', 'usage_count')
    op.drop_column('arenas', 'source_pool_challenge_id')
    op.drop_column('arenas', 'is_public')
