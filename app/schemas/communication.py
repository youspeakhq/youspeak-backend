from typing import Optional, List, Dict
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

from app.models.enums import ArenaStatus, AnnouncementType, NotificationChannel

# --- Arena ---
class ArenaCreate(BaseModel):
    title: str
    mode: str = 'class' # not in enum yet, maybe add to model or use just description
    rules: List[str] = []
    criteria: Dict[str, int] # name: weight

class ArenaSchedule(BaseModel):
    start_time: datetime
    duration_min: int

class ArenaResponse(BaseModel):
    id: UUID
    title: str
    status: ArenaStatus
    start_time: Optional[datetime]
    
    class Config:
        from_attributes = True

# --- Announcement ---
class AnnouncementCreate(BaseModel):
    title: str
    body: str
    class_ids: List[UUID] = []
    attachments: List[str] = [] # URLs
    is_reminder: bool = False
    reminder_date: Optional[datetime] = None

class AnnouncementResponse(BaseModel):
    id: UUID
    type: AnnouncementType
    message: str
    created_at: datetime
    author_name: str
    
    class Config:
        from_attributes = True
