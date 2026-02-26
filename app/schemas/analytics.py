"""Schemas for analytics and room monitor (learning sessions).

Aligned with Figma Room Monitor frame: header with tabs, row of class cards,
and Class Performance Summary section with 'see all'. See docs/figma-cache/3543-5489.json.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import SessionStatus, SessionType


class LearningSessionCreate(BaseModel):
    session_type: SessionType


class LearningSessionOut(BaseModel):
    id: UUID
    class_id: UUID
    started_by_user_id: Optional[UUID] = None
    session_type: SessionType
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: SessionStatus

    model_config = ConfigDict(from_attributes=True)


class RoomMonitorCard(BaseModel):
    """One room/class card for the Room Monitor dashboard (Figma: row of 3 cards)."""
    class_id: UUID
    class_name: str
    student_count: int
    active_session: Optional[LearningSessionOut] = None


class ClassPerformanceSummary(BaseModel):
    """Class Performance Summary section (Figma: block with 'see all')."""
    recent_sessions_count: int = 0
    recent_sessions: List[LearningSessionOut] = []


class RoomMonitorResponse(BaseModel):
    """Room monitor detail for one class: card data plus optional performance summary."""
    class_id: UUID
    class_name: str
    student_count: int
    active_session: Optional[LearningSessionOut] = None
    performance_summary: Optional[ClassPerformanceSummary] = None
