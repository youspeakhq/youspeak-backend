"""Arena service SQLAlchemy models — standalone, no core app dependency."""

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, Table, Boolean
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from .base import BaseModel, Base
from .enums import ArenaStatus


class Arena(BaseModel):
    __tablename__ = "arenas"

    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(ENUM(ArenaStatus, name="arena_status", create_type=False), default=ArenaStatus.DRAFT, nullable=False, index=True)
    start_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)

    arena_mode = Column(String(20), nullable=True)
    judging_mode = Column(String(20), nullable=True)
    ai_co_judge_enabled = Column(Boolean, default=False, nullable=False)
    student_selection_mode = Column(String(20), nullable=True)
    session_state = Column(String(20), default='not_started', nullable=False, index=True)
    team_size = Column(Integer, nullable=True)

    join_code = Column(String(20), nullable=True, unique=True)
    qr_code_url = Column(Text, nullable=True)
    join_code_expires_at = Column(DateTime, nullable=True)

    realtimekit_meeting_id = Column(String(255), nullable=True)
    recording_started_at = Column(DateTime, nullable=True)
    recording_stopped_at = Column(DateTime, nullable=True)
    recording_url = Column(Text, nullable=True)
    recording_status = Column(String(20), default='not_started', nullable=False)
    transcription_status = Column(String(20), default='not_started', nullable=False)
    transcription_url = Column(Text, nullable=True)

    is_public = Column(Boolean, default=False, nullable=False)
    source_pool_challenge_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="SET NULL"), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    published_at = Column(DateTime, nullable=True)
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    waiting_room_entries = relationship("ArenaWaitingRoom", back_populates="arena", lazy="select")
    participants = relationship("ArenaParticipant", back_populates="arena", lazy="noload", cascade="all, delete-orphan")
    reactions = relationship("ArenaReaction", back_populates="arena", lazy="noload", cascade="all, delete-orphan")
    teams = relationship("ArenaTeam", back_populates="arena", lazy="noload", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Arena {self.title}>"


class ArenaWaitingRoom(BaseModel):
    __tablename__ = "arena_waiting_room"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_timestamp = Column(DateTime, nullable=False)
    status = Column(String(20), default='pending', nullable=False)
    admitted_at = Column(DateTime, nullable=True)
    admitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)

    arena = relationship("Arena", back_populates="waiting_room_entries")

    def __repr__(self):
        return f"<ArenaWaitingRoom arena={self.arena_id} student={self.student_id} status={self.status}>"


class ArenaParticipant(BaseModel):
    __tablename__ = "arena_participants"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default='participant', nullable=False)
    team_id = Column(UUID(as_uuid=True), nullable=True)
    is_speaking = Column(Boolean, default=False, nullable=False)
    speaking_start_time = Column(DateTime, nullable=True)
    total_speaking_duration_seconds = Column(Integer, default=0, nullable=False)
    engagement_score = Column(Numeric(5, 2), default=0.00, nullable=False)
    ai_pronunciation_score = Column(Numeric(5, 2), nullable=True)
    ai_fluency_score = Column(Numeric(5, 2), nullable=True)
    teacher_rating = Column(Numeric(5, 2), nullable=True)
    teacher_feedback = Column(Text, nullable=True)
    last_activity = Column(DateTime, nullable=False)

    arena = relationship("Arena", back_populates="participants")

    def __repr__(self):
        return f"<ArenaParticipant arena={self.arena_id} student={self.student_id} speaking={self.is_speaking}>"


class ArenaReaction(BaseModel):
    __tablename__ = "arena_reactions"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    target_participant_id = Column(UUID(as_uuid=True), ForeignKey("arena_participants.id", ondelete="CASCADE"), nullable=True)
    reaction_type = Column(String(20), nullable=False)
    timestamp = Column(DateTime, nullable=False)

    arena = relationship("Arena", back_populates="reactions")


class ArenaTeam(BaseModel):
    __tablename__ = "arena_teams"

    arena_id = Column(UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), nullable=False, index=True)
    team_name = Column(String(50), nullable=False)

    arena = relationship("Arena", back_populates="teams")
    members = relationship("ArenaTeamMember", back_populates="team", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ArenaTeam {self.team_name}>"


class ArenaTeamMember(BaseModel):
    __tablename__ = "arena_team_members"

    team_id = Column(UUID(as_uuid=True), ForeignKey("arena_teams.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default='member', nullable=False)

    team = relationship("ArenaTeam", back_populates="members")

    def __repr__(self):
        return f"<ArenaTeamMember student={self.student_id} role={self.role}>"
