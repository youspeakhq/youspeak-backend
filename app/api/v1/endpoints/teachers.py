from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.services.user_service import UserService
from app.services.school_service import SchoolService
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

from datetime import datetime, timedelta
from app.models.access_code import TeacherAccessCode
from app.core import security

# ...

@router.post("", response_model=SuccessResponse)
async def create_teacher_invite(
    teacher_in: TeacherCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create teacher (generates invite with Access Code).
    """
    # Check if user exists
    existing_user = await UserService.get_user_by_email(db, teacher_in.email)
    if existing_user:
         raise HTTPException(status_code=400, detail="User with this email already exists")

    # Generate Access Code
    code = security.generate_access_code()
    
    access_code = TeacherAccessCode(
        code=code,
        school_id=current_user.school_id,
        created_by_admin_id=current_user.id,
        # We don't store email in AccessCode model currently, but we could sending email mock here
        expires_at=datetime.utcnow() + timedelta(days=7),
        is_used=False
    )
    
    db.add(access_code)
    await db.commit()
    
    # In a real app, successful response would be void (email sent), 
    # but for Development/Testing we return the code.
    return SuccessResponse(
        data={"access_code": code},
        message=f"Invite created for {teacher_in.email}"
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
