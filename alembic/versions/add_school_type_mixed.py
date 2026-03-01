"""Add school_type value 'mixed'

Product decision: school types are Primary, Secondary, Mixed (not Tertiary).
PostgreSQL/asyncpg require the new enum value to be committed before use, so we
commit after ADD VALUE; the tertiary->mixed backfill is in the next migration.
"""
from alembic import op
from sqlalchemy import text

revision = "g6h7i8j9k0l1"
down_revision = "8ad49556d467"
branch_labels = None
depends_on = None

# Disable transaction for this migration to allow ALTER TYPE
disable_transaction = True

def upgrade() -> None:
    op.execute("ALTER TYPE school_type ADD VALUE IF NOT EXISTS 'mixed'")


def downgrade() -> None:
    pass  # PostgreSQL does not support removing enum values
