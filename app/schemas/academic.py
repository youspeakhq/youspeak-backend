from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime, time, date

from app.models.enums import DayOfWeek, ClassStatus, StudentRole

class ScheduleBase(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time

class ClassBase(BaseModel):
    name: str
    sub_class: Optional[str] = None
    description: Optional[str] = None
    status: ClassStatus = ClassStatus.ACTIVE

class ClassCreate(ClassBase):
    level: Optional[str] = None # Mapped to sub_class or description? Spec says 'level'
    schedule: List[ScheduleBase]
    language_id: int
    semester_id: UUID

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[ClassStatus] = None

class RosterUpdate(BaseModel):
    student_id: UUID
    role: StudentRole

class ClassResponse(ClassBase):
    id: UUID
    school_id: UUID
    semester_id: UUID
    language_id: int
    schedules: List[ScheduleBase] = []
    
    class Config:
        from_attributes = True

class ClassWithStats(ClassResponse):
    student_count: int = 0
