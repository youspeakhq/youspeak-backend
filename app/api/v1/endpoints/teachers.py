import secrets
from datetime import timedelta
from app.utils.time import get_utc_now
from typing import Any
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.models.access_code import TeacherAccessCode
from app.core import security
from app.services.user_service import UserService
from app.services.academic_service import AcademicService
from app.services.email_service import send_teacher_invite
from app.schemas.student import TeacherCreate
from app.schemas.user import UserResponse, TeacherResponse
from app.schemas.responses import SuccessResponse, PaginatedResponse

router = APIRouter()


@router.get("", response_model=PaginatedResponse[TeacherResponse])
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
        status=status,
    )

    # Load class assignments for all teachers in one query.
    teacher_class_map: dict = {}
    if teachers:
        from sqlalchemy import select
        from app.models.academic import teacher_assignments, Class
        teacher_ids = [u.id for u in teachers]
        stmt = (
            select(teacher_assignments.c.teacher_id, Class.id)
            .join(Class, Class.id == teacher_assignments.c.class_id)
            .where(teacher_assignments.c.teacher_id.in_(teacher_ids))
        )
        rows = (await db.execute(stmt)).all()
        for row in rows:
            teacher_class_map.setdefault(row.teacher_id, []).append(str(row[1]))

    # Build response dicts while the DB session is still open so that
    # relationships are accessible without lazy loading.
    def _teacher_dict(u: User) -> TeacherResponse:
        return TeacherResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            role=u.role,
            school_id=u.school_id,
            profile_picture_url=u.profile_picture_url,
            student_number=None,
            is_verified=True,
            created_at=u.created_at,
            updated_at=u.updated_at,
            last_login=getattr(u, "last_login", None),
            class_ids=teacher_class_map.get(u.id, []),
        )

    serialized = [_teacher_dict(u) for u in teachers]
    total = len(teachers)
    return PaginatedResponse(
        data=serialized,
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
        expires_at=get_utc_now() + timedelta(days=7),
        is_used=False,
    )
    db.add(access_code)

    # Assign teacher to classes if provided
    if teacher_in.class_ids:
        success = await AcademicService.assign_teacher_to_classes(
            db, teacher.id, teacher_in.class_ids, current_user.school_id
        )
        if not success:
            raise HTTPException(
                status_code=400,
                detail="One or more class IDs are invalid or don't belong to this school",
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


@router.post("/import", response_model=SuccessResponse)
async def import_teachers_csv(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
    file: UploadFile = File(...),
) -> Any:
    """
    Bulk import teachers from CSV.
    Columns: first_name, last_name, email.
    Creates invited teachers (is_active=False) and sends invite emails.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported. Use columns: first_name, last_name, email.",
        )
    content = await file.read()
    result = await UserService.import_teachers_from_csv(
        db, content, current_user.school_id, current_user.id
    )
    for inv in result.get("invitations", []):
        background_tasks.add_task(
            send_teacher_invite,
            inv["email"],
            inv["first_name"],
            inv["code"],
        )
    msg = f"Imported: {result['created']} created, {result['skipped']} skipped."
    if result.get("errors"):
        msg += f" Errors: {'; '.join(result['errors'][:5])}"
        if len(result["errors"]) > 5:
            msg += f" (+{len(result['errors']) - 5} more)"
    return SuccessResponse(data=result, message=msg)


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
