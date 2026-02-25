from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

from app.models.enums import ArenaStatus, AnnouncementType

# --- Arena ---


class ArenaCreate(BaseModel):
    class_id: UUID
    title: str
    description: Optional[str] = None
    rules: List[str] = []
    criteria: Dict[str, int]  # name -> weight_percentage
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaSchedule(BaseModel):
    start_time: datetime
    duration_min: int


class ArenaUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ArenaStatus] = None
    rules: Optional[List[str]] = None
    criteria: Optional[Dict[str, int]] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaListRow(BaseModel):
    id: UUID
    title: str
    status: ArenaStatus
    class_id: UUID
    class_name: Optional[str] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None


class ArenaResponse(BaseModel):
    id: UUID
    class_id: UUID
    title: str
    description: Optional[str] = None
    status: ArenaStatus
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    criteria: List[Dict[str, object]]  # [{"name": str, "weight_percentage": int}]
    rules: List[str]

    model_config = ConfigDict(from_attributes=True)

# --- Announcement ---


class AnnouncementCreate(BaseModel):
    title: str
    body: str
    class_ids: List[UUID] = []
    attachments: List[str] = []  # URLs
    is_reminder: bool = False
    reminder_date: Optional[datetime] = None


class AnnouncementResponse(BaseModel):
    id: UUID
    type: AnnouncementType
    message: str
    created_at: datetime
    author_name: str

    model_config = ConfigDict(from_attributes=True)
