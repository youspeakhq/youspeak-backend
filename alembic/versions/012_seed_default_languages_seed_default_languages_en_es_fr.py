"""seed default languages en es fr

Revision ID: 012_seed_default_languages
Revises: 011_remove_classrooms
Create Date: 2026-04-20 00:00:47.674980

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '012_seed_default_languages'
down_revision = '011_remove_classrooms'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO languages (name, code, is_active)
        VALUES
            ('English', 'en', true),
            ('Spanish', 'es', true),
            ('French', 'fr', true)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM languages WHERE code IN ('en', 'es', 'fr')")
