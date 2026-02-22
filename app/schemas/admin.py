"""Admin dashboard schemas."""

from datetime import datetime
from uuid import UUID
from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import ActivityActionType


class AdminStats(BaseModel):
    """
    Aggregated dashboard statistics for a school.
    Returned by GET /api/v1/admin/stats.
    """

    active_classes: int = Field(
        ...,
        ge=0,
        description="Number of classes with status ACTIVE (non-archived)",
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Number of active, non-deleted students enrolled at the school",
    )
    total_teachers: int = Field(
        ...,
        ge=0,
        description="Number of active, non-deleted teachers at the school",
    )


class LeaderboardStudentEntry(BaseModel):
    """One row in the students leaderboard (Figma: Student, Class, Points)."""

    rank: int = Field(..., ge=1, description="1-based rank")
    student_id: UUID = Field(..., description="Student user id")
    student_name: str = Field(..., description="Full name for display")
    class_id: UUID = Field(..., description="Class id (primary class for this student)")
    class_name: str = Field(..., description="Class display name e.g. French 101 - A")
    points: float = Field(..., ge=0, description="Total arena points in the timeframe")


class LeaderboardClassEntry(BaseModel):
    """One row in the top classes leaderboard."""

    rank: int = Field(..., ge=1, description="1-based rank")
    class_id: UUID = Field(..., description="Class id")
    class_name: str = Field(..., description="Class display name")
    score: float = Field(..., ge=0, description="Aggregated points for the class in the timeframe")


class LeaderboardResponse(BaseModel):
    """Response for GET /admin/leaderboard aligned with Figma (Students leaderboard + top classes)."""

    top_students: list[LeaderboardStudentEntry] = Field(
        default_factory=list,
        description="Students leaderboard: Student, Class, Points",
    )
    top_classes: list[LeaderboardClassEntry] = Field(
        default_factory=list,
        description="Top performing classes by aggregated points",
    )
    timeframe: str = Field(..., description="week | month | all")


# Activity log
class ActivityLogCreate(BaseModel):
    """Payload for POST /admin/activity."""

    action_type: ActivityActionType = Field(..., description="Type of action")
    description: str = Field(..., min_length=1, max_length=2000, description="Human-readable description for the feed")
    target_entity_type: Optional[str] = Field(None, max_length=64, description="e.g. class, student, teacher")
    target_entity_id: Optional[UUID] = Field(None, description="ID of the affected entity if any")
    metadata: Optional[dict[str, Any]] = Field(None, description="Optional extra data")


class ActivityLogOut(BaseModel):
    """One activity log entry for GET /admin/activity."""

    id: UUID
    action_type: ActivityActionType
    description: str
    performed_by_user_id: Optional[UUID] = None
    performer_name: Optional[str] = Field(None, description="Full name of user who performed the action")
    target_entity_type: Optional[str] = None
    target_entity_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
