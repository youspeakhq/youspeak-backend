"""Unit tests for UserResponse schema — classrooms field."""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.academic import ClassroomBrief
from app.schemas.user import UserResponse
from app.models.enums import UserRole, ProficiencyLevel


# ---------------------------------------------------------------------------
# ClassroomBrief schema
# ---------------------------------------------------------------------------

def test_classroom_brief_valid():
    cid = uuid4()
    brief = ClassroomBrief(
        id=cid,
        name="French Beginners",
        level=ProficiencyLevel.A1,
        language_id=2,
    )
    assert brief.id == cid
    assert brief.name == "French Beginners"
    assert brief.level == ProficiencyLevel.A1
    assert brief.language_id == 2


def test_classroom_brief_all_levels():
    """ClassroomBrief accepts every ProficiencyLevel value."""
    for level in ProficiencyLevel:
        brief = ClassroomBrief(id=uuid4(), name="Room", level=level, language_id=1)
        assert brief.level == level


def test_classroom_brief_from_orm_like_dict():
    """ClassroomBrief.model_validate works with ORM-style dict (from_attributes)."""
    cid = uuid4()

    class FakeClassroom:
        id = cid
        name = "Spanish Advanced"
        level = ProficiencyLevel.C1
        language_id = 3

    brief = ClassroomBrief.model_validate(FakeClassroom())
    assert brief.id == cid
    assert brief.name == "Spanish Advanced"
    assert brief.level == ProficiencyLevel.C1


# ---------------------------------------------------------------------------
# UserResponse.classrooms field
# ---------------------------------------------------------------------------

def _make_now():
    return datetime.now(tz=timezone.utc)


def _base_user_payload(**overrides):
    payload = dict(
        id=uuid4(),
        email="student@school.com",
        full_name="Jane Doe",
        is_active=True,
        role=UserRole.STUDENT,
        school_id=uuid4(),
        profile_picture_url=None,
        student_number="2025-001",
        is_verified=False,
        created_at=_make_now(),
        updated_at=_make_now(),
        last_login=None,
    )
    payload.update(overrides)
    return payload


def test_user_response_classrooms_defaults_to_empty_list():
    """When no classrooms provided, field defaults to []."""
    user = UserResponse(**_base_user_payload())
    assert user.classrooms == []


def test_user_response_classrooms_with_one_classroom():
    classroom = ClassroomBrief(
        id=uuid4(), name="French A1", level=ProficiencyLevel.A1, language_id=1
    )
    user = UserResponse(**_base_user_payload(classrooms=[classroom]))
    assert len(user.classrooms) == 1
    assert user.classrooms[0].name == "French A1"


def test_user_response_classrooms_with_multiple_classrooms():
    classrooms = [
        ClassroomBrief(id=uuid4(), name=f"Room {i}", level=ProficiencyLevel.B1, language_id=i)
        for i in range(1, 4)
    ]
    user = UserResponse(**_base_user_payload(classrooms=classrooms))
    assert len(user.classrooms) == 3
    assert user.classrooms[2].name == "Room 3"


def test_user_response_serialises_classrooms_to_dict():
    """model_dump includes classrooms with expected keys."""
    cid = uuid4()
    classroom = ClassroomBrief(id=cid, name="German B2", level=ProficiencyLevel.B2, language_id=5)
    user = UserResponse(**_base_user_payload(classrooms=[classroom]))
    d = user.model_dump()
    assert "classrooms" in d
    assert d["classrooms"][0]["name"] == "German B2"
    assert d["classrooms"][0]["language_id"] == 5


def test_user_response_non_student_classrooms_defaults_empty():
    """Teacher role also has classrooms field (defaulting to []) — no errors."""
    user = UserResponse(**_base_user_payload(role=UserRole.TEACHER, student_number=None))
    assert user.classrooms == []
