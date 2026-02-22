"""Add ActivityLog model for admin dashboard activity feed.

Revision ID: a1b2c3d4e5f6
Revises: 7f081ab2c64e
Create Date: 2026-02-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision = "a1b2c3d4e5f6"
down_revision = "7f081ab2c64e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    exists = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'activity_logs'"
            )
        ).scalar()
        is not None
    )
    if not exists:
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE activity_action_type AS ENUM ("
            "'student_registered', 'student_removed', 'class_created', 'class_archived',"
            "'teacher_invited', 'teacher_joined', 'curriculum_published', 'arena_scheduled',"
            "'arena_completed', 'other'"
            "); "
            "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
        )
        op.create_table(
            "activity_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("school_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column(
                "action_type",
                postgresql.ENUM(
                    "student_registered",
                    "student_removed",
                    "class_created",
                    "class_archived",
                    "teacher_invited",
                    "teacher_joined",
                    "curriculum_published",
                    "arena_scheduled",
                    "arena_completed",
                    "other",
                    name="activity_action_type",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("performed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("target_entity_type", sa.String(64), nullable=True),
            sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.ForeignKeyConstraint(["school_id"], ["schools.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["performed_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_activity_logs_id"), "activity_logs", ["id"], unique=False)
        op.create_index(op.f("ix_activity_logs_school_id"), "activity_logs", ["school_id"], unique=False)
        op.create_index(op.f("ix_activity_logs_action_type"), "activity_logs", ["action_type"], unique=False)
        op.create_index(op.f("ix_activity_logs_performed_by_user_id"), "activity_logs", ["performed_by_user_id"], unique=False)
        op.create_index(op.f("ix_activity_logs_target_entity_type"), "activity_logs", ["target_entity_type"], unique=False)
        op.create_index(op.f("ix_activity_logs_target_entity_id"), "activity_logs", ["target_entity_id"], unique=False)
        op.create_index(op.f("ix_activity_logs_created_at"), "activity_logs", ["created_at"], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    exists = (
        conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'activity_logs'"
            )
        ).scalar()
        is not None
    )
    if exists:
        op.drop_index(op.f("ix_activity_logs_created_at"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_target_entity_id"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_target_entity_type"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_performed_by_user_id"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_action_type"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_school_id"), table_name="activity_logs")
        op.drop_index(op.f("ix_activity_logs_id"), table_name="activity_logs")
        op.drop_table("activity_logs")
        op.execute("DROP TYPE IF EXISTS activity_action_type")
