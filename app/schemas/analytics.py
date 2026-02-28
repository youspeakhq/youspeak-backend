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


class RoomMonitorStats(BaseModel):
    """KPI stats for Room Monitor top row (Figma: Total Learning Sessions, Active Students, Avg. Session Duration)."""
    total_sessions: int = 0
    active_students: int = 0
    avg_session_duration_minutes: Optional[float] = None


class ClassPerformanceSummaryRow(BaseModel):
    """One row in the Class Performance Summary table (Figma)."""
    class_id: UUID
    class_name: str
    student_count: int
    module_progress_pct: Optional[int] = None
    module_progress_label: Optional[str] = None
    avg_quiz_score_pct: Optional[float] = None
    time_spent_minutes_per_student: Optional[float] = None
    last_activity_at: Optional[datetime] = None
    active_session: Optional[LearningSessionOut] = None
