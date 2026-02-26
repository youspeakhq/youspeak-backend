"""merge_heads

Revision ID: 8ad49556d467
Revises: add_ai_marking, a1b2c3d4e5f7
Create Date: 2026-02-26 17:54:32.921438

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8ad49556d467'
down_revision = ('add_ai_marking', 'a1b2c3d4e5f7')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
