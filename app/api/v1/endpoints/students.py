from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.services.user_service import UserService
from app.schemas.user import UserResponse
from app.schemas.student import StudentCreate, StudentUpdate
from app.schemas.responses import SuccessResponse, PaginatedResponse

router = APIRouter()

@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_students(
    page: int = 1,
    limit: int = 50,
    status: str = "active",
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List all students.
    """
    # Simplified pagination - robust implementation would use offset/limit query
    all_students = await UserService.get_users_by_school_and_role(
        db, 
        current_user.school_id, 
        UserRole.STUDENT,
        include_deleted=(status == "deleted")
    )
    
    # Manual pagination for now
    start = (page - 1) * limit
    end = start + limit
    paginated = all_students[start:end]
    
    return PaginatedResponse(
        data=paginated,
        meta={
            "page": page,
            "limit": limit,
            "total": len(all_students),
            "pages": (len(all_students) + limit - 1) // limit
        }
    )

@router.post("", response_model=SuccessResponse[UserResponse])
async def create_student(
    student_in: StudentCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create single student.
    """
    # Create user logic here, linking to class if provided
    # ...
    
    return SuccessResponse(message="Student created successfully")

@router.delete("/{student_id}", response_model=SuccessResponse)
async def delete_student(
    student_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Soft Delete: Move to Trash.
    """
    success = await UserService.soft_delete_user(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
        
    return SuccessResponse(message="Student moved to trash")

@router.post("/{student_id}/restore", response_model=SuccessResponse)
async def restore_student(
    student_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Restore from Trash.
    """
    success = await UserService.restore_user(db, student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found or not deleted")
        
    return SuccessResponse(message="Student restored successfully")
