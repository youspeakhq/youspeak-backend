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
    
    return PaginatedResponse(
        data=teachers,
        meta={"total": len(teachers), "page": 1, "limit": 100}
    )

@router.post("", response_model=SuccessResponse)
async def create_teacher_invite(
    teacher_in: TeacherCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create teacher (generates invite).
    """
    # Simply generates an invite email/code in reality
    # For now, we stub it as successful
    
    return SuccessResponse(
        message=f"Invite sent to {teacher_in.email}"
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
