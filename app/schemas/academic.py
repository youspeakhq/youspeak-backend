


from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import time

from app.models.enums import DayOfWeek, ClassStatus, ProficiencyLevel, StudentRole


class ScheduleBase(BaseModel):
    day_of_week: DayOfWeek
    start_time: time
    end_time: time

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "day_of_week": "Mon",
                "start_time": "09:00:00",
                "end_time": "10:00:00"
            }
        }
    )


class ClassBase(BaseModel):
    name: str
    sub_class: Optional[str] = None
    description: Optional[str] = None
    timeline: Optional[str] = None
    status: ClassStatus = ClassStatus.ACTIVE


class ClassCreate(ClassBase):
    level: Optional[ProficiencyLevel] = None
    schedule: List[ScheduleBase]
    language_id: int
    term_id: UUID

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "French 101",
                    "description": "Beginner French class",
                    "timeline": "Spring 2026",
                    "schedule": [
                        {
                            "day_of_week": "Mon",
                            "start_time": "09:00:00",
                            "end_time": "10:00:00"
                        },
                        {
                            "day_of_week": "Wed",
                            "start_time": "09:00:00",
                            "end_time": "10:00:00"
                        }
                    ],
                    "language_id": 1,
                    "term_id": "123e4567-e89b-12d3-a456-426614174000",
                    "status": "active"
                }
            ]
        }
    )


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    sub_class: Optional[str] = None
    description: Optional[str] = None
    timeline: Optional[str] = None
    status: Optional[ClassStatus] = None
    level: Optional[ProficiencyLevel] = None
    schedule: Optional[List[ScheduleBase]] = None


class RosterUpdate(BaseModel):
    student_id: UUID
    role: StudentRole


class AssignTeacherRequest(BaseModel):
    teacher_id: UUID


class ClassResponse(ClassBase):
    id: UUID
    school_id: UUID
    term_id: UUID
    language_id: int
    level: Optional[ProficiencyLevel] = None
    schedules: List[ScheduleBase] = []

    model_config = ConfigDict(from_attributes=True)


class ClassWithStats(ClassResponse):
    student_count: int = 0
