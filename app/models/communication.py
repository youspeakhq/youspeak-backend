"""Domain 7: Communication Models (Announcements & Notifications)"""

from sqlalchemy import Column, Text, DateTime, Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID, ENUM, ARRAY
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import AnnouncementType, NotificationChannel, EmailSendStatus


class Announcement(BaseModel, SchoolScopedMixin):
    """
    Unified announcement and notification system.
    Supports school-wide and class-specific announcements.
    """
    __tablename__ = "announcements"

    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=True, index=True)
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=True, index=True)

    type = Column(ENUM(AnnouncementType, name="announcement_type"), nullable=False)
    message = Column(Text, nullable=False)

    # Relationships
    school = relationship("School", back_populates="announcements")
    author = relationship("User", back_populates="authored_announcements")
    class_ = relationship("Class", back_populates="announcements")
    reminders = relationship("AnnouncementReminder", back_populates="announcement", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Announcement {self.type}>"


class AnnouncementReminder(BaseModel):
    """
    Scheduled reminders for announcements.
    Supports multiple channels (in-app, email, push).
    """
    __tablename__ = "announcement_reminders"

    announcement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("announcements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scheduled_at = Column(DateTime, nullable=False)
    reminder_message = Column(Text, nullable=True)  # Override default message
    is_sent = Column(Boolean, default=False, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    channel = Column(ENUM(NotificationChannel, name="notification_channel"), nullable=False)

    # Relationships
    announcement = relationship("Announcement", back_populates="reminders")

    def __repr__(self) -> str:
        return f"<AnnouncementReminder {self.channel} - {'Sent' if self.is_sent else 'Pending'}>"


class EmailLog(BaseModel):
    """
    Email audit trail for all emails sent through the API.
    Tracks sender, recipients, and delivery status for compliance and debugging.
    """
    __tablename__ = "email_logs"

    school_id = Column(UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), nullable=True, index=True)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipients = Column(ARRAY(Text), nullable=False)
    subject = Column(Text, nullable=False)
    html_body_sha256 = Column(String(64), nullable=False)
    send_status = Column(ENUM(EmailSendStatus, name="email_send_status", native_enum=True, values_callable=lambda obj: [e.value for e in obj]), default=EmailSendStatus.PENDING, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    # Relationships
    sender = relationship("User", back_populates="sent_emails")
    school = relationship("School", back_populates="email_logs")

    def __repr__(self) -> str:
        return f"<EmailLog {self.send_status} to {len(self.recipients)} recipients>"
