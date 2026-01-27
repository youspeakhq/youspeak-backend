"""Domain 6: Arena (Gamification) Models"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, Table
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


# Association table for Arena <-> Moderator (Teachers/Admins)
arena_moderators = Table(
    "arena_moderators",
    BaseModel.metadata,
    Column("arena_id", UUID(as_uuid=True), ForeignKey("arenas.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
)
