"""Domain 8: Analytics & Room Activity Models"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.enums import SessionType, SessionStatus


class LearningSession(BaseModel):
    """
    Live learning session/room activity tracking.
    Monitors classroom engagement and practice sessions.
    """
    __tablename__ = "learning_sessions"
    
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    started_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    session_type = Column(ENUM(SessionType, name="session_type"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(ENUM(SessionStatus, name="session_status"), default=SessionStatus.IN_PROGRESS, nullable=False)
    
    # Relationships
    class_ = relationship("Class", back_populates="learning_sessions")
    started_by_user = relationship("User", back_populates="started_sessions")
    
    def __repr__(self) -> str:
        return f"<LearningSession {self.session_type} - {self.status}>"


class Award(BaseModel):
    """
    Student recognition and achievements.
    E.g., "Star of the Week", performance badges.
    """
    __tablename__ = "awards"
    
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)  # e.g., "Star of the Week"
    description = Column(Text, nullable=True)
    criteria = Column(Text, nullable=True)  # What they did to earn it
    awarded_at = Column(DateTime, nullable=False)
    
    # Relationships
    student = relationship("User", back_populates="awards")
    class_ = relationship("Class", back_populates="awards")
    
    def __repr__(self) -> str:
        return f"<Award {self.title} to {self.student_id}>"
