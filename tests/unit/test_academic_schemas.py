"""Unit tests for academic schemas (Classroom, Class, etc.)."""

import pytest
from uuid import uuid4

from app.schemas.academic import (
    ClassroomCreate,
    ClassroomUpdate,
    ClassroomAddTeacher,
    ClassroomAddStudent,
    ClassCreate,
    ScheduleBase,
)
from app.models.enums import DayOfWeek, ProficiencyLevel


def test_classroom_create_valid():
    data = ClassroomCreate(
        name="AP Chinese Language",
        language_id=1,
        level=ProficiencyLevel.B1,
    )
    assert data.name == "AP Chinese Language"
    assert data.language_id == 1
    assert data.level == ProficiencyLevel.B1


def test_classroom_create_all_levels():
    for level in ProficiencyLevel:
        data = ClassroomCreate(
            name=f"Class {level.value}",
            language_id=1,
            level=level,
        )
        assert data.level == level


def test_classroom_update_partial():
    data = ClassroomUpdate(name="Updated Name")
    assert data.name == "Updated Name"
    assert data.level is None


def test_classroom_add_teacher():
    tid = uuid4()
    data = ClassroomAddTeacher(teacher_id=tid)
    assert data.teacher_id == tid


def test_classroom_add_student():
    sid = uuid4()
    data = ClassroomAddStudent(student_id=sid)
    assert data.student_id == sid


def test_class_create_with_classroom_id():
    sem_id = uuid4()
    data = ClassCreate(
        name="French 101",
        schedule=[
            ScheduleBase(day_of_week=DayOfWeek.MONDAY, start_time="09:00:00", end_time="10:00:00")
        ],
        language_id=1,
        semester_id=sem_id,
        classroom_id=uuid4(),
    )
    assert data.classroom_id is not None


def test_class_create_without_classroom_id():
    sem_id = uuid4()
    data = ClassCreate(
        name="French 101",
        schedule=[
            ScheduleBase(day_of_week=DayOfWeek.MONDAY, start_time="09:00:00", end_time="10:00:00")
        ],
        language_id=1,
        semester_id=sem_id,
    )
    assert data.classroom_id is None


def test_schedule_base_time_parsing():
    s = ScheduleBase(
        day_of_week=DayOfWeek.WEDNESDAY,
        start_time="14:30:00",
        end_time="15:45:00",
    )
    assert s.day_of_week == DayOfWeek.WEDNESDAY
    assert str(s.start_time) == "14:30:00"
    assert str(s.end_time) == "15:45:00"
