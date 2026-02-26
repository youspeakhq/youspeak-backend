"""Backfill school_type: set tertiary -> mixed

Runs in a separate migration so the new enum value 'mixed' is committed first.
"""
from alembic import op

revision = "h7i8j9k0l1m2"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE schools SET school_type = 'mixed' WHERE school_type::text = 'tertiary'"
    )


def downgrade() -> None:
    pass  # No revert for data change
