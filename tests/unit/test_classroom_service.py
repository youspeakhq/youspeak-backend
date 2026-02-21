"""Unit tests for ClassroomService."""

import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.classroom_service import ClassroomService
from app.models.enums import UserRole
from app.models.academic import Classroom
from app.models.user import User

@pytest.mark.asyncio
async def test_add_teacher_to_classroom_success():
    # Setup mocks
    db = AsyncMock(spec=AsyncSession)
    school_id = uuid4()
    classroom_id = uuid4()
    teacher_id = uuid4()
    
    classroom = Classroom(id=classroom_id, school_id=school_id)
    user = User(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
    
    with patch("app.services.classroom_service.ClassroomService.get_classroom_by_id", new_callable=AsyncMock) as mock_get_room:
        mock_get_room.return_value = classroom
        with patch("app.services.classroom_service.UserService.get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = user
            
            # Mock existing check (no assignment exists)
            from unittest.mock import MagicMock
            mock_result = MagicMock()
            mock_result.first.return_value = None
            db.execute.return_value = mock_result
            
            # Call service
            result = await ClassroomService.add_teacher_to_classroom(
                db=db,
                classroom_id=classroom_id,
                teacher_id=teacher_id,
                school_id=school_id
            )
            
            assert result is True
            assert db.execute.called
            assert db.commit.called


@pytest.mark.asyncio
async def test_add_teacher_to_classroom_invalid_role():
    # Setup mocks
    db = AsyncMock(spec=AsyncSession)
    school_id = uuid4()
    classroom_id = uuid4()
    teacher_id = uuid4()
    
    classroom = Classroom(id=classroom_id, school_id=school_id)
    user = User(id=teacher_id, school_id=school_id, role=UserRole.STUDENT) # Wrong role
    
    with patch("app.services.classroom_service.ClassroomService.get_classroom_by_id", new_callable=AsyncMock) as mock_get_room:
        mock_get_room.return_value = classroom
        with patch("app.services.classroom_service.UserService.get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = user
            
            # Call service
            result = await ClassroomService.add_teacher_to_classroom(
                db=db,
                classroom_id=classroom_id,
                teacher_id=teacher_id,
                school_id=school_id
            )
            
            assert result is False
            assert not db.commit.called


@pytest.mark.asyncio
async def test_add_teacher_to_classroom_already_assigned():
    # Setup mocks
    db = AsyncMock(spec=AsyncSession)
    school_id = uuid4()
    classroom_id = uuid4()
    teacher_id = uuid4()
    
    classroom = Classroom(id=classroom_id, school_id=school_id)
    user = User(id=teacher_id, school_id=school_id, role=UserRole.TEACHER)
    
    with patch("app.services.classroom_service.ClassroomService.get_classroom_by_id", new_callable=AsyncMock) as mock_get_room:
        mock_get_room.return_value = classroom
        with patch("app.services.classroom_service.UserService.get_user_by_id", new_callable=AsyncMock) as mock_get_user:
            mock_get_user.return_value = user
            
            # Mock existing check (assignment ALREADY exists)
            mock_result = AsyncMock()
            mock_result.first.return_value = ("already_exists",)
            db.execute.return_value = mock_result
            
            # Call service
            result = await ClassroomService.add_teacher_to_classroom(
                db=db,
                classroom_id=classroom_id,
                teacher_id=teacher_id,
                school_id=school_id
            )
            
            assert result is False
            assert not db.commit.called
