"""Admin dashboard schemas."""

from pydantic import BaseModel, Field


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
