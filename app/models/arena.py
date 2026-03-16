"""Domain 6: Arena (Gamification) Models"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, Table, Boolean
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.enums import ArenaStatus


class Arena(BaseModel):
    """
    Live speaking challenge/competition.
    Gamification feature for student engagement.
    """
    __tablename__ = "arenas"

    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(ENUM(ArenaStatus, name="arena_status"), default=ArenaStatus.DRAFT, nullable=False, index=True)
    start_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    # Phase 1: Session configuration fields
    arena_mode = Column(String(20), nullable=True)  # 'competitive' | 'collaborative'
    judging_mode = Column(String(20), nullable=True)  # 'teacher_only' | 'hybrid'
    ai_co_judge_enabled = Column(Boolean, default=False, nullable=False)
    student_selection_mode = Column(String(20), nullable=True)  # 'manual' | 'hybrid' | 'randomize'
    session_state = Column(String(20), default='not_started', nullable=False, index=True)  # 'not_started' | 'initialized' | 'live' | 'completed'
    team_size = Column(Integer, nullable=True)  # For collaborative mode (2-5)

    # Phase 2: Waiting room & admission
    join_code = Column(String(20), nullable=True, unique=True)  # 6-digit code for students to join
    qr_code_url = Column(Text, nullable=True)  # URL to QR code image
    join_code_expires_at = Column(DateTime, nullable=True)  # Expiration timestamp

    # Relationships
    class_ = relationship("Class", back_populates="arenas")
    criteria = relationship("ArenaCriteria", back_populates="arena", cascade="all, delete-orphan")
    rules = relationship("ArenaRule", back_populates="arena", cascade="all, delete-orphan")
    performers = relationship("ArenaPerformer", back_populates="arena", cascade="all, delete-orphan")
    moderators = relationship(
        "User",
        secondary="arena_moderators",
        backref="moderated_arenas"
    )

    def __repr__(self) -> str:
        return f"<Arena {self.title}>"


class ArenaCriteria(BaseModel):
    """
    Scoring criteria for arena challenges.
    Defines what is measured and weighted.
    """
    __tablename__ = "arena_criteria"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)  # e.g., "Pronunciation", "Fluency"
    weight_percentage = Column(Integer, nullable=False)  # e.g., 40 for 40%

    # Relationships
    arena = relationship("Arena", back_populates="criteria")

    def __repr__(self) -> str:
        return f"<ArenaCriteria {self.name} ({self.weight_percentage}%)>"


class ArenaRule(BaseModel):
    """
    Rules and guidelines for arena challenges.
    """
    __tablename__ = "arena_rules"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(Text, nullable=False)

    # Relationships
    arena = relationship("Arena", back_populates="rules")

    def __repr__(self) -> str:
        return f"<ArenaRule for Arena {self.arena_id}>"


class ArenaPerformer(BaseModel):
    """
    Student participant in an arena challenge.
    Tracks performance and scoring.
    """
    __tablename__ = "arena_performers"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    total_points = Column(Numeric(10, 2), default=0.0, nullable=False)

    # Relationships
    arena = relationship("Arena", back_populates="performers")
    user = relationship("User", back_populates="arena_performances")

    def __repr__(self) -> str:
        return f"<ArenaPerformer {self.user_id} - {self.total_points} pts>"


class ArenaWaitingRoom(BaseModel):
    """
    Students waiting to be admitted to an arena session.
    Phase 2: Waiting room & admission control.
    """
    __tablename__ = "arena_waiting_room"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_timestamp = Column(DateTime, nullable=False)
    status = Column(String(20), default='pending', nullable=False)  # 'pending' | 'admitted' | 'rejected'
    admitted_at = Column(DateTime, nullable=True)
    admitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    # Relationships
    arena = relationship("Arena", backref="waiting_room_entries")
    student = relationship("User", foreign_keys=[student_id], backref="arena_waiting_entries")
    admitted_by_user = relationship("User", foreign_keys=[admitted_by])

    def __repr__(self) -> str:
        return f"<ArenaWaitingRoom arena={self.arena_id} student={self.student_id} status={self.status}>"


class ArenaParticipant(BaseModel):
    """
    Live session participant tracking.
    Phase 4: Tracks speaking time, engagement, and real-time state.
    """
    __tablename__ = "arena_participants"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default='participant', nullable=False)  # 'participant' | 'audience'
    team_id = Column(UUID(as_uuid=True), nullable=True)  # For Phase 6 collaborative mode
    is_speaking = Column(Boolean, default=False, nullable=False)
    speaking_start_time = Column(DateTime, nullable=True)
    total_speaking_duration_seconds = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Numeric(5, 2), default=0.00, nullable=False)  # 0.00 to 100.00
    last_activity = Column(DateTime, nullable=False)

    # Relationships
    arena = relationship("Arena", backref="participants")
    student = relationship("User", backref="arena_participations")

    def __repr__(self) -> str:
        return f"<ArenaParticipant arena={self.arena_id} student={self.student_id} speaking={self.is_speaking}>"


class ArenaReaction(BaseModel):
    """
    Real-time reactions sent during live sessions.
    Phase 4: Emoji reactions, applause, etc.
    """
    __tablename__ = "arena_reactions"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_participant_id = Column(UUID(as_uuid=True), ForeignKey("arena_participants.id", ondelete="CASCADE"), nullable=True)
    reaction_type = Column(String(20), nullable=False)  # 'heart' | 'clap' | 'laugh' | 'thumbs_up'
    timestamp = Column(DateTime, nullable=False)

    # Relationships
    arena = relationship("Arena", backref="reactions")
    user = relationship("User", backref="sent_reactions")
    target_participant = relationship("ArenaParticipant", backref="received_reactions")

    def __repr__(self) -> str:
        return f"<ArenaReaction {self.reaction_type} from {self.user_id}>"


# Association table for Arena <-> Moderator (Teachers/Admins)
arena_moderators = Table(
    "arena_moderators",
    BaseModel.metadata,
    Column("arena_id", UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
)
