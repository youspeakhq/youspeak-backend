"""Classroom endpoints - Admin creates and manages classrooms"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.services.classroom_service import ClassroomService
from app.schemas.academic import ClassroomCreate, ClassroomAddTeacher, ClassroomAddStudent
from app.schemas.responses import SuccessResponse

router = APIRouter()


@router.get("", response_model=SuccessResponse)
async def list_classrooms(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List all classrooms for the school. Admin only."""
    classrooms = await ClassroomService.list_classrooms(db, current_user.school_id)
    return SuccessResponse(data=classrooms)


@router.post("", response_model=SuccessResponse)
async def create_classroom(
    classroom_in: ClassroomCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create a new classroom. Admin only. Fields: name, language_id, level."""
    classroom = await ClassroomService.create_classroom(
        db, current_user.school_id, classroom_in
    )
    return SuccessResponse(
        data={
            "id": classroom.id,
            "name": classroom.name,
            "language_id": classroom.language_id,
            "level": classroom.level.value,
            "school_id": classroom.school_id,
        },
        message="Classroom created successfully",
    )


@router.get("/{classroom_id}", response_model=SuccessResponse)
async def get_classroom(
    classroom_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get classroom by ID. Admin only."""
    classroom = await ClassroomService.get_classroom_by_id(
        db, classroom_id, current_user.school_id
    )
    if not classroom:
        raise HTTPException(status_code=404, detail="Classroom not found")
    from sqlalchemy import select, func
    from app.models.academic import classroom_teachers, classroom_students
    teacher_count = await db.scalar(
        select(func.count()).select_from(classroom_teachers).where(
            classroom_teachers.c.classroom_id == classroom_id
        )
    )
    student_count = await db.scalar(
        select(func.count()).select_from(classroom_students).where(
            classroom_students.c.classroom_id == classroom_id
        )
    )
    return SuccessResponse(
        data={
            "id": classroom.id,
            "name": classroom.name,
            "language_id": classroom.language_id,
            "level": classroom.level.value,
            "school_id": classroom.school_id,
            "teacher_count": teacher_count or 0,
            "student_count": student_count or 0,
        }
    )


@router.post("/{classroom_id}/teachers", response_model=SuccessResponse)
async def add_teacher_to_classroom(
    classroom_id: UUID,
    body: ClassroomAddTeacher,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Add teacher to classroom. Admin only."""
    success = await ClassroomService.add_teacher_to_classroom(
        db, classroom_id, body.teacher_id, current_user.school_id
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not add teacher. Teacher may not exist or already assigned.",
        )
    return SuccessResponse(message="Teacher added to classroom")


@router.post("/{classroom_id}/students", response_model=SuccessResponse)
async def add_student_to_classroom(
    classroom_id: UUID,
    body: ClassroomAddStudent,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Add student to classroom. Admin only."""
    success = await ClassroomService.add_student_to_classroom(
        db, classroom_id, body.student_id, current_user.school_id
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not add student. Student may not exist or already assigned.",
        )
    return SuccessResponse(message="Student added to classroom")
