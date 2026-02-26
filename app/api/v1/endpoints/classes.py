from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.schemas.academic import ClassResponse, ClassCreate, RosterUpdate
from app.schemas.admin import LeaderboardResponse
from app.schemas.analytics import (
    ClassPerformanceSummary,
    LearningSessionCreate,
    LearningSessionOut,
    RoomMonitorCard,
    RoomMonitorResponse,
)
from app.schemas.award import AwardCreate, AwardOut
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services.academic_service import AcademicService
from app.services.award_service import AwardService
from app.services.learning_session_service import LearningSessionService
from app.services.school_service import SchoolService

router = APIRouter()

VALID_LEADERBOARD_TIMEFRAMES = {"week", "month", "all"}


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


@router.get("/leaderboard", response_model=SuccessResponse[LeaderboardResponse])
async def get_my_classes_leaderboard(
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
    timeframe: str = Query("week", description="week | month | all"),
) -> Any:
    """
    Leaderboard for the teacher's classes only (Figma: Leaderboards and awards).
    Timeframe: week | month | all.
    """
    if timeframe not in VALID_LEADERBOARD_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe must be one of: {', '.join(sorted(VALID_LEADERBOARD_TIMEFRAMES))}",
        )
    teacher_classes = await AcademicService.get_teacher_classes(db, current_user.id)
    class_ids = [c.id for c in teacher_classes]
    data = await SchoolService.get_leaderboard(
        db, current_user.school_id, timeframe=timeframe, class_ids=class_ids
    )
    return SuccessResponse(data=data, message="Leaderboard retrieved successfully")


@router.get("/awards", response_model=PaginatedResponse[AwardOut])
async def list_my_class_awards(
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    student_id: Optional[UUID] = Query(None, description="Filter by student"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Any:
    """
    List awards for the teacher's classes (Figma: Leaderboard awards cards).
    """
    items, total = await AwardService.list_teacher_awards(
        db, current_user.id, class_id=class_id, student_id=student_id, page=page, page_size=page_size
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[AwardOut(**x) for x in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
        message="Awards retrieved successfully",
    )


@router.post("/awards", response_model=SuccessResponse[List[AwardOut]])
async def create_awards(
    payload: AwardCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create new award(s) (Figma: Create New Award – Award name, Criteria, Associated class(es), Select student(s)).
    Creates one award per (student, class) for each selected student enrolled in each selected class.
    """
    created, err = await AwardService.create_awards(db, current_user.id, current_user.school_id, payload)
    if err:
        raise HTTPException(status_code=400, detail=err)
    out = [
        AwardOut(
            id=a.id,
            student_id=a.student_id,
            class_id=a.class_id,
            title=a.title,
            description=a.description,
            criteria=a.criteria,
            awarded_at=a.awarded_at,
        )
        for a in created
    ]
    return SuccessResponse(data=out, message=f"{len(out)} award(s) created successfully")


@router.post("", response_model=SuccessResponse[ClassResponse])
async def create_class(
    class_in: ClassCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create new class.
    """
    try:
        new_class = await AcademicService.create_class(
            db,
            current_user.school_id,
            class_in,
            teacher_id=current_user.id,
        )
        return SuccessResponse(data=new_class, message="Class created successfully")
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Invalid data provided, e.g., nonexistent semester_id or language_id.")


@router.get("/monitor", response_model=SuccessResponse[List[RoomMonitorCard]])
async def list_room_monitor_cards(
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Room monitor dashboard: one card per class the teacher teaches (Figma: row of class cards).
    """
    cards_data = await LearningSessionService.list_monitor_cards_for_teacher(db, current_user.id)
    data = [
        RoomMonitorCard(
            class_id=cid,
            class_name=cname,
            student_count=count,
            active_session=LearningSessionOut.model_validate(active) if active else None,
        )
        for cid, cname, count, active in cards_data
    ]
    return SuccessResponse(data=data, message="Room monitor cards retrieved successfully")


@router.get("/{class_id}/monitor", response_model=SuccessResponse[RoomMonitorResponse])
async def get_room_monitor(
    class_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Room monitor detail for one class: card data plus Class Performance Summary (Figma: detail + summary section).
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    teacher_classes = await AcademicService.get_teacher_classes(db, current_user.id)
    if not any(c.id == class_id for c in teacher_classes):
        raise HTTPException(status_code=404, detail="Class not found")
    roster = await AcademicService.get_class_roster(db, class_id)
    active = await LearningSessionService.get_active_session(db, class_id)
    recent_sessions = await LearningSessionService.list_sessions_for_class(
        db, class_id, current_user.id, limit=5
    )
    performance_summary = ClassPerformanceSummary(
        recent_sessions_count=len(recent_sessions),
        recent_sessions=[LearningSessionOut.model_validate(s) for s in recent_sessions],
    )
    data = RoomMonitorResponse(
        class_id=class_id,
        class_name=cls.name,
        student_count=len(roster),
        active_session=LearningSessionOut.model_validate(active) if active else None,
        performance_summary=performance_summary,
    )
    return SuccessResponse(data=data, message="Room monitor retrieved successfully")


@router.get("/{class_id}/sessions", response_model=SuccessResponse[List[LearningSessionOut]])
async def list_class_sessions(
    class_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """
    List learning sessions for a class (most recent first).
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    sessions = await LearningSessionService.list_sessions_for_class(
        db, class_id, current_user.id, limit=limit
    )
    return SuccessResponse(
        data=[LearningSessionOut.model_validate(s) for s in sessions],
        message="Sessions retrieved successfully",
    )


@router.post("/{class_id}/sessions", response_model=SuccessResponse[LearningSessionOut])
async def start_class_session(
    class_id: UUID,
    body: LearningSessionCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Start a learning session for the class. Only one active session per class at a time.
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    session = await LearningSessionService.start_session(
        db, class_id, current_user.id, body.session_type
    )
    if not session:
        raise HTTPException(
            status_code=400,
            detail="Class not found, access denied, or a session is already in progress.",
        )
    return SuccessResponse(
        data=LearningSessionOut.model_validate(session),
        message="Session started successfully",
    )


@router.patch("/{class_id}/sessions/{session_id}", response_model=SuccessResponse)
async def end_class_session(
    class_id: UUID,
    session_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    End an in-progress learning session.
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    ok = await LearningSessionService.end_session(db, session_id, class_id, current_user.id)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Session not found, already ended, or access denied.",
        )
    return SuccessResponse(data={}, message="Session ended successfully")


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


@router.post("/{class_id}/roster/import", response_model=SuccessResponse)
async def import_class_roster(
    class_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Bulk import students from CSV. Supports PDF, Docs, CSV per frontend.
    Currently CSV only. Columns: first_name, last_name, email (optional).
    Creates new students or enrolls existing ones in the class.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV files are supported. Use columns: first_name, last_name, email."
        )
    content = await file.read()
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    teacher_classes = await AcademicService.get_teacher_classes(db, current_user.id)
    if not any(c.id == class_id for c in teacher_classes):
        raise HTTPException(status_code=404, detail="Class not found")
    result = await AcademicService.import_roster_from_csv(
        db, class_id, content, current_user.school_id, cls.language_id
    )
    msg = f"Imported: {result['enrolled']} enrolled, {result['created']} created, {result['skipped']} skipped."
    if result["errors"]:
        msg += f" Errors: {'; '.join(result['errors'][:5])}"
        if len(result["errors"]) > 5:
            msg += f" (+{len(result['errors']) - 5} more)"
    return SuccessResponse(data=result, message=msg)
