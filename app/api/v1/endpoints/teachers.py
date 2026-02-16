import secrets
from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.models.access_code import TeacherAccessCode
from app.core import security
from app.services.user_service import UserService
from app.services.classroom_service import ClassroomService
from app.services.email_service import send_teacher_invite
from app.schemas.student import TeacherCreate
from app.schemas.user import UserResponse
from app.schemas.responses import SuccessResponse, PaginatedResponse

router = APIRouter()

@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_teachers(
    status: str = "active",
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List all teachers.
    """
    teachers = await UserService.get_users_by_school_and_role(
        db, 
        current_user.school_id, 
        UserRole.TEACHER,
        include_deleted=(status == "deleted")
    )
    
    total = len(teachers)
    return PaginatedResponse(
        data=teachers,
        meta={
            "page": 1,
            "page_size": 100,
            "total": total,
            "total_pages": 1 if total > 0 else 0
        }
    )

@router.post("", response_model=SuccessResponse)
async def create_teacher_invite(
    teacher_in: TeacherCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Admin creates teacher (is_active=False). Generates invite code, sends email.
    Teacher activates account at POST /auth/register/teacher with the code.
    Optionally assign to classrooms via classroom_ids.
    """
    existing_user = await UserService.get_user_by_email(db, teacher_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    placeholder = secrets.token_hex(32)
    teacher = await UserService.create_invited_teacher(
        db=db,
        email=teacher_in.email,
        first_name=teacher_in.first_name,
        last_name=teacher_in.last_name,
        school_id=current_user.school_id,
        placeholder_password=placeholder,
    )

    code = security.generate_access_code()
    access_code = TeacherAccessCode(
        code=code,
        school_id=current_user.school_id,
        created_by_admin_id=current_user.id,
        invited_teacher_id=teacher.id,
        expires_at=datetime.utcnow() + timedelta(days=7),
        is_used=False,
    )
    db.add(access_code)

    if teacher_in.classroom_ids:
        for cid in teacher_in.classroom_ids:
            await ClassroomService.add_teacher_to_classroom(
                db, cid, teacher.id, current_user.school_id
            )

    await db.commit()

    background_tasks.add_task(
        send_teacher_invite,
        teacher_in.email,
        teacher_in.first_name,
        code,
    )

    return SuccessResponse(
        data={"access_code": code, "teacher_id": str(teacher.id)},
        message=f"Teacher created. Invite sent to {teacher_in.email}. Activate via code.",
    )

@router.delete("/{teacher_id}", response_model=SuccessResponse)
async def delete_teacher(
    teacher_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Soft Delete: Move to Trash.
    """
    success = await UserService.soft_delete_user(db, teacher_id)
    if not success:
        raise HTTPException(status_code=404, detail="Teacher not found")
        
    return SuccessResponse(message="Teacher moved to trash")
