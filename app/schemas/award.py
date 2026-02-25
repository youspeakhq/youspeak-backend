"""Award schemas (Figma: Create New Award – Leaderboard module)."""

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class AwardCreate(BaseModel):
    """Payload for POST /my-classes/awards (Create New Award)."""

    title: str = Field(..., min_length=1, max_length=255, description="Award name")
    criteria: Optional[str] = Field(None, max_length=2000, description="What they did to earn it")
    class_ids: list[UUID] = Field(..., min_length=1, description="Associated class(es)")
    student_ids: list[UUID] = Field(..., min_length=1, description="Select student(s) to award")


class AwardOut(BaseModel):
    """One award for list/detail responses."""

    id: UUID
    student_id: UUID
    class_id: UUID
    title: str
    description: Optional[str] = None
    criteria: Optional[str] = None
    awarded_at: datetime
    student_name: Optional[str] = Field(None, description="Full name for display")
    class_name: Optional[str] = Field(None, description="Class display name")

    model_config = ConfigDict(from_attributes=True)
