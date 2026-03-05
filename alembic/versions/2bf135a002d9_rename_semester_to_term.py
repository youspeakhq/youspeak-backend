"""rename_semester_to_term

Revision ID: 2bf135a002d9
Revises: 84d9cb7499cd
Create Date: 2026-03-05 13:49:06.404340

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2bf135a002d9'
down_revision = '84d9cb7499cd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Rename semesters table to terms
    op.rename_table('semesters', 'terms')
    
    # 2. Rename indexes and constraints on terms table
    op.execute("ALTER INDEX ix_semesters_id RENAME TO ix_terms_id")
    op.execute("ALTER INDEX ix_semesters_is_active RENAME TO ix_terms_is_active")
    op.execute("ALTER INDEX ix_semesters_school_id RENAME TO ix_terms_school_id")
    op.execute("ALTER TABLE terms RENAME CONSTRAINT semesters_pkey TO terms_pkey")
    op.execute("ALTER TABLE terms RENAME CONSTRAINT semesters_school_id_fkey TO terms_school_id_fkey")

    # 3. Rename semester_id column in classes table to term_id
    op.alter_column('classes', 'semester_id', new_column_name='term_id')
    
    # 4. Rename index and foreign key on classes table
    op.execute("ALTER INDEX ix_classes_semester_id RENAME TO ix_classes_term_id")
    op.execute("ALTER TABLE classes RENAME CONSTRAINT classes_semester_id_fkey TO classes_term_id_fkey")


def downgrade() -> None:
    # 1. Rename term_id column back to semester_id
    op.alter_column('classes', 'term_id', new_column_name='semester_id')
    
    # 2. Rename index and foreign key on classes table back
    op.execute("ALTER INDEX ix_classes_term_id RENAME TO ix_classes_semester_id")
    op.execute("ALTER TABLE classes RENAME CONSTRAINT classes_term_id_fkey TO classes_semester_id_fkey")

    # 3. Rename terms table back to semesters
    op.rename_table('terms', 'semesters')
    
    # 4. Rename indexes and constraints on semesters table back
    op.execute("ALTER INDEX ix_terms_id RENAME TO ix_semesters_id")
    op.execute("ALTER INDEX ix_terms_is_active RENAME TO ix_semesters_is_active")
    op.execute("ALTER INDEX ix_terms_school_id RENAME TO ix_semesters_school_id")
    op.execute("ALTER TABLE semesters RENAME CONSTRAINT terms_pkey TO semesters_pkey")
    op.execute("ALTER TABLE semesters RENAME CONSTRAINT terms_school_id_fkey TO semesters_school_id_fkey")
