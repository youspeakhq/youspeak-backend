"""merge_heads

Revision ID: 574b256045e7
Revises: add_task_category, e7f8a9b0c1d2
Create Date: 2026-03-05 12:28:27.030996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '574b256045e7'
down_revision = ('add_task_category', 'e7f8a9b0c1d2')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
