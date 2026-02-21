from typing import Any, List
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
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
        status=status,
    )
    
    # Manual pagination for now
    start = (page - 1) * limit
    end = start + limit
    paginated = all_students[start:end]
    
    total = len(all_students)
    total_pages = (total + limit - 1) // limit if limit > 0 else 0

    # Build response dicts while the DB session is still open so that
    # selectinload-populated enrolled_classrooms is accessible without lazy loading.
    from app.schemas.academic import ClassroomBrief

    def _student_dict(u: User) -> dict:
        classrooms = [
            ClassroomBrief.model_validate(c)
            for c in (u.enrolled_classrooms or [])
        ]
        return UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            role=u.role,
            school_id=u.school_id,
            profile_picture_url=u.profile_picture_url,
            student_number=u.student_number,
            is_verified=False,
            created_at=u.created_at,
            updated_at=u.updated_at,
            last_login=getattr(u, "last_login", None),
            classrooms=classrooms,
        )

    serialized = [_student_dict(u) for u in paginated]
    return PaginatedResponse(
        data=serialized,
        meta={
            "page": page,
            "page_size": limit,
            "total": total,
            "total_pages": total_pages
        }
    )

from app.services.academic_service import AcademicService
import secrets

# ...

@router.post("", response_model=SuccessResponse[UserResponse])
async def create_student(
    student_in: StudentCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create single student.
    """
    email = student_in.email
    if not email:
        suffix = secrets.token_hex(4)
        email = f"{student_in.first_name.lower()}.{student_in.last_name.lower()}.{suffix}@youspeak-dummy.com"
        
    password = student_in.password or "Student123!"

    # Check email uniqueness (UserService might handle, but good to check)
    existing = await UserService.get_user_by_email(db, email)
    if existing:
        if student_in.email:
             raise HTTPException(status_code=400, detail="Student email already exists")
        else:
             # If generated, regenerate (simple retry or fail)
             suffix = secrets.token_hex(4)
             email = f"{student_in.first_name.lower()}.{student_in.last_name.lower()}.{suffix}@youspeak-dummy.com"

    student_number = (student_in.student_id or "").strip() or None

    try:
        user = await UserService.create_user(
            db=db,
            email=email,
            password=password,
            first_name=student_in.first_name,
            last_name=student_in.last_name,
            school_id=current_user.school_id,
            role=UserRole.STUDENT,
            is_active=True,
            student_number=student_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Enroll in class
    if student_in.class_id:
        await AcademicService.add_student_to_class(db, student_in.class_id, user.id)
    
    return SuccessResponse(data=UserResponse.model_validate(user), message="Student created successfully")


@router.post("/import", response_model=SuccessResponse)
async def import_students_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Bulk import students from CSV.
    Columns: first_name, last_name, email (optional), student_id (optional), class_id (optional).
    student_id: human-readable ID (e.g. 2025-001). Auto-generated if omitted.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported. Use columns: first_name, last_name, email, student_id (optional), class_id (optional).",
        )
    content = await file.read()
    result = await AcademicService.import_students_from_csv(
        db, content, current_user.school_id
    )
    msg = f"Imported: {result['created']} created, {result['enrolled']} enrolled, {result['skipped']} skipped."
    if result.get("errors"):
        msg += f" Errors: {'; '.join(result['errors'][:5])}"
        if len(result["errors"]) > 5:
            msg += f" (+{len(result['errors']) - 5} more)"
    return SuccessResponse(data=result, message=msg)


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
        
    return SuccessResponse(data=None, message="Student moved to trash")

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
        
    return SuccessResponse(data=None, message="Student restored successfully")

@router.post("/trash/cleanup", response_model=SuccessResponse)
async def cleanup_trash(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Permanently wipe expired trash (30+ days old).
    """
    count = await UserService.cleanup_expired_trash(db)
    return SuccessResponse(data=None, message=f"Cleaned up {count} expired student records")
