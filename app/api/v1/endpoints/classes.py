from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.services.academic_service import AcademicService
from app.schemas.academic import ClassResponse, ClassCreate, RosterUpdate
from app.schemas.responses import SuccessResponse

router = APIRouter()

@router.get("", response_model=SuccessResponse[List[ClassResponse]])
async def get_my_classes(
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List assigned classes.
    """
    classes = await AcademicService.get_teacher_classes(db, current_user.id)
    return SuccessResponse(data=classes)

@router.post("", response_model=SuccessResponse[ClassResponse])
async def create_class(
    class_in: ClassCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create new class.
    """
    # Ideally check permission settings if teachers can create classes
    new_class = await AcademicService.create_class(
        db, 
        current_user.school_id, 
        class_in
    )
    return SuccessResponse(data=new_class, message="Class created successfully")

@router.get("/{class_id}/roster", response_model=SuccessResponse)
async def get_class_roster(
    class_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List students with Roles.
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    teacher_classes = await AcademicService.get_teacher_classes(db, current_user.id)
    if not any(c.id == class_id for c in teacher_classes):
        raise HTTPException(status_code=404, detail="Class not found")
    roster = await AcademicService.get_class_roster(db, class_id)
    return SuccessResponse(data=roster)

@router.post("/{class_id}/roster", response_model=SuccessResponse)
async def add_student_to_roster(
    class_id: UUID,
    roster_in: RosterUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Add student with specific role.
    """
    success = await AcademicService.add_student_to_class(
        db, class_id, roster_in.student_id, roster_in.role
    )
    if not success:
        raise HTTPException(status_code=400, detail="Could not add student")
        
    return SuccessResponse(message="Student added to class")
