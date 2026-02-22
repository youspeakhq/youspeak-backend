"""Admin activity log: school-wide audit trail for dashboard."""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import ActivityActionType


class ActivityLog(BaseModel, SchoolScopedMixin):
    """
    Append-only log of notable actions within a school.
    Powers the admin dashboard Activity Log (Figma).
    """
    __tablename__ = "activity_logs"

    action_type = Column(
        ENUM(
            ActivityActionType,
            name="activity_action_type",
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=False)
    performed_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_entity_type = Column(String(64), nullable=True, index=True)
    target_entity_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_ = Column("metadata", JSONB, nullable=True)

    school = relationship("School", back_populates="activity_logs")
    performed_by = relationship("User", back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog {self.action_type.value} @ {self.created_at}>"
