"""Model for tracking trashed students with auto-wipe logic."""

from datetime import datetime, timedelta, timezone
from app.utils.time import get_utc_now
from sqlalchemy import Column, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel


class StudentTrash(BaseModel):
    """
    Tracks students moved to trash.
    Enforces a 30-day retention policy.
    """
    __tablename__ = "student_trash"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    deleted_at = Column(DateTime, default=get_utc_now, nullable=False)
    expires_at = Column(
        DateTime,
        default=lambda: get_utc_now() + timedelta(days=30),
        nullable=False,
        index=True
    )

    # Relationship back to User
    user = relationship("User", backref="trash_record")

    def __repr__(self) -> str:
        return f"<StudentTrash user_id={self.user_id} expires_at={self.expires_at}>"
