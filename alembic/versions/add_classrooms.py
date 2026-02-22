"""add classrooms table and classroom_id to classes

Revision ID: c3d4e5f6a7b8
Revises: d0e1f2a3b4c5
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


revision = "c3d4e5f6a7b8"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE proficiency_level AS ENUM ("
        "'beginner', 'a1', 'a2', 'b1', 'b2', 'intermediate', 'c1'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    conn = op.get_bind()
    has_classrooms = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'classrooms'"
            )
        ).scalar()
        is not None
    )
    if not has_classrooms:
        op.create_table(
            "classrooms",
            sa.Column("language_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("level", postgresql.ENUM("beginner", "a1", "a2", "b1", "b2", "intermediate", "c1",
                      name="proficiency_level", create_type=False), nullable=False),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("school_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["language_id"], ["languages.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_classrooms_id"), "classrooms", ["id"], unique=False)
        op.create_index(op.f("ix_classrooms_language_id"), "classrooms", ["language_id"], unique=False)
        op.create_index(op.f("ix_classrooms_level"), "classrooms", ["level"], unique=False)
        op.create_index(op.f("ix_classrooms_school_id"), "classrooms", ["school_id"], unique=False)

        op.create_table(
            "classroom_teachers",
            sa.Column("classroom_id", sa.UUID(), nullable=False),
            sa.Column("teacher_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("classroom_id", "teacher_id"),
        )
        op.create_table(
            "classroom_students",
            sa.Column("classroom_id", sa.UUID(), nullable=False),
            sa.Column("student_id", sa.UUID(), nullable=False),
            sa.ForeignKeyConstraint(["classroom_id"], ["classrooms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("classroom_id", "student_id"),
        )

    has_classroom_id = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'classes' AND column_name = 'classroom_id'"
            )
        ).scalar()
        is not None
    )
    if not has_classroom_id:
        op.add_column(
            "classes",
            sa.Column("classroom_id", sa.UUID(), nullable=True),
        )
        op.create_foreign_key(
            "fk_classes_classroom_id",
            "classes",
            "classrooms",
            ["classroom_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(op.f("ix_classes_classroom_id"), "classes", ["classroom_id"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    has_classroom_id = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'classes' AND column_name = 'classroom_id'"
            )
        ).scalar()
        is not None
    )
    if has_classroom_id:
        op.drop_index(op.f("ix_classes_classroom_id"), table_name="classes")
        op.drop_constraint("fk_classes_classroom_id", "classes", type_="foreignkey")
        op.drop_column("classes", "classroom_id")

    has_classrooms = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'classrooms'"
            )
        ).scalar()
        is not None
    )
    if has_classrooms:
        op.drop_table("classroom_students")
        op.drop_table("classroom_teachers")
        op.drop_index(op.f("ix_classrooms_school_id"), table_name="classrooms")
        op.drop_index(op.f("ix_classrooms_level"), table_name="classrooms")
        op.drop_index(op.f("ix_classrooms_language_id"), table_name="classrooms")
        op.drop_index(op.f("ix_classrooms_id"), table_name="classrooms")
        op.drop_table("classrooms")
    op.execute("DROP TYPE IF EXISTS proficiency_level")
