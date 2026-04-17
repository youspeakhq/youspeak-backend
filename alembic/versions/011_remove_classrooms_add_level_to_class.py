"""Remove classrooms tables and add level column to classes

Revision ID: 011_remove_classrooms
Revises: 010_ai_scores
Create Date: 2026-04-17

Path A: Removes the Classroom concept entirely.
- Drops classroom_students and classroom_teachers association tables.
- Drops classrooms table.
- Adds level (proficiency_level enum) column to classes table.
- Removes classroom_id FK column from classes table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '011_remove_classrooms'
down_revision = '010_ai_scores'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add level column to classes (nullable so existing rows aren't broken)
    #    The proficiency_level enum already exists in the DB from classrooms.
    op.add_column(
        'classes',
        sa.Column(
            'level',
            sa.Enum(
                'beginner', 'a1', 'a2', 'b1', 'b2', 'intermediate', 'c1',
                name='proficiency_level',
                create_type=False,  # enum already exists
            ),
            nullable=True,
        )
    )

    # 2. Back-fill level on any class that was linked to a classroom
    #    so we don't lose proficiency data.
    op.execute("""
        UPDATE classes c
        SET level = cr.level
        FROM classrooms cr
        WHERE c.classroom_id = cr.id
          AND c.classroom_id IS NOT NULL
          AND c.level IS NULL
    """)

    # 3. Drop classroom_id FK and column from classes
    #    (constraint name may vary — use IF EXISTS via raw SQL to be safe)
    op.execute("""
        DO $$
        DECLARE
            r RECORD;
        BEGIN
            FOR r IN
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'classes'::regclass
                  AND contype = 'f'
                  AND conname LIKE '%classroom%'
            LOOP
                EXECUTE 'ALTER TABLE classes DROP CONSTRAINT IF EXISTS ' || quote_ident(r.conname);
            END LOOP;
        END $$;
    """)
    op.drop_index(op.f('ix_classes_classroom_id'), table_name='classes', if_exists=True)
    op.drop_column('classes', 'classroom_id')

    # 4. Drop association tables (must come before classrooms table)
    op.drop_table('classroom_students')
    op.drop_table('classroom_teachers')

    # 5. Drop classrooms table
    op.drop_table('classrooms')


def downgrade() -> None:
    # Recreate classrooms table
    op.create_table(
        'classrooms',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('language_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column(
            'level',
            sa.Enum('beginner', 'a1', 'a2', 'b1', 'b2', 'intermediate', 'c1',
                    name='proficiency_level', create_type=False),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['language_id'], ['languages.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['school_id'], ['schools.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'classroom_teachers',
        sa.Column('classroom_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('teacher_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['classroom_id'], ['classrooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('classroom_id', 'teacher_id'),
    )

    op.create_table(
        'classroom_students',
        sa.Column('classroom_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['classroom_id'], ['classrooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('classroom_id', 'student_id'),
    )

    # Restore classroom_id on classes
    op.add_column(
        'classes',
        sa.Column('classroom_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'classes_classroom_id_fkey', 'classes', 'classrooms',
        ['classroom_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_classes_classroom_id', 'classes', ['classroom_id'])

    # Remove level column from classes
    op.drop_column('classes', 'level')
