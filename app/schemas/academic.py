from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime, time, date

from app.models.enums import DayOfWeek, ClassStatus, ProficiencyLevel, StudentRole


class ClassroomBase(BaseModel):
    name: str
    language_id: int
    level: ProficiencyLevel


class ClassroomCreate(ClassroomBase):
    pass


class ClassroomBrief(BaseModel):
    """Minimal classroom info for embedding in student/teacher responses."""
    id: UUID
    name: str
    level: ProficiencyLevel
    language_id: int

    model_config = ConfigDict(from_attributes=True)


class ClassroomUpdate(BaseModel):
    name: Optional[str] = None
    level: Optional[ProficiencyLevel] = None


class ClassroomResponse(ClassroomBase):
    id: UUID
    school_id: UUID
    teacher_count: int = 0
    student_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class ClassroomAddTeacher(BaseModel):
    teacher_id: UUID


class ClassroomAddStudent(BaseModel):
    student_id: UUID

class ScheduleBase(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time

class ClassBase(BaseModel):
    name: str
    sub_class: Optional[str] = None
    description: Optional[str] = None
    timeline: Optional[str] = None
    status: ClassStatus = ClassStatus.ACTIVE

class ClassCreate(ClassBase):
    level: Optional[str] = None
    schedule: List[ScheduleBase]
    language_id: int
    semester_id: UUID
    classroom_id: Optional[UUID] = None

class ClassUpdate(BaseModel):
    name: Optional[str] = None
    timeline: Optional[str] = None
    status: Optional[ClassStatus] = None

class RosterUpdate(BaseModel):
    student_id: UUID
    role: StudentRole

class ClassResponse(ClassBase):
    id: UUID
    school_id: UUID
    semester_id: UUID
    language_id: int
    classroom_id: Optional[UUID] = None
    schedules: List[ScheduleBase] = []

    model_config = ConfigDict(from_attributes=True)

class ClassWithStats(ClassResponse):
    student_count: int = 0
