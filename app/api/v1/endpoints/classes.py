import json
from typing import Any, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.schemas.academic import ClassResponse, ClassCreate, RosterUpdate
from app.schemas.admin import LeaderboardResponse
from app.schemas.analytics import (
    ClassPerformanceSummary,
    ClassPerformanceSummaryRow,
    LearningSessionCreate,
    LearningSessionOut,
    RoomMonitorCard,
    RoomMonitorResponse,
    RoomMonitorStats,
)
from app.schemas.award import AwardCreate, AwardOut
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services.academic_service import AcademicService
from app.services.award_service import AwardService
from app.services.learning_session_service import LearningSessionService
from app.services.school_service import SchoolService

router = APIRouter()

VALID_LEADERBOARD_TIMEFRAMES = {"week", "month", "all"}


async def _parse_multipart_class_request(form: Any) -> Tuple[ClassCreate, Optional[bytes]]:
    """Parse multipart form: required 'data' (class JSON), optional 'file' (CSV)."""
    data_value = form.get("data")
    if data_value is None or (isinstance(data_value, str) and not data_value.strip()):
        raise HTTPException(
            status_code=400,
            detail="Multipart requests must include a 'data' field with class JSON.",
        )
    if isinstance(data_value, str):
        data_str = data_value
    elif hasattr(data_value, "read"):
        data_str = (await data_value.read()).decode("utf-8")
    else:
        data_str = getattr(data_value, "value", data_value)
    if not isinstance(data_str, str):
        raise HTTPException(status_code=400, detail="Field 'data' must be a JSON string.")
    try:
        class_data = ClassCreate.model_validate(json.loads(data_str))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in 'data': {e}") from e
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    roster_bytes: Optional[bytes] = None
    file_part = form.get("file")
    if file_part is not None and getattr(file_part, "filename", None):
        if not str(file_part.filename).lower().endswith(".csv"):
            raise HTTPException(
                status_code=400,
                detail="Only CSV files are supported for roster import.",
            )
        roster_bytes = await file_part.read()
    return class_data, roster_bytes


async def parse_create_class_request(request: Request) -> Tuple[ClassCreate, Optional[bytes]]:
    """Parse create-class body: JSON (ClassCreate only) or multipart (data + optional CSV file)."""
    ct = request.headers.get("content-type", "")
    if "application/json" in ct:
        body = await request.json()
        return ClassCreate.model_validate(body), None
    if "multipart/form-data" in ct:
        form = await request.form()
        return await _parse_multipart_class_request(form)
    raise HTTPException(
        status_code=400,
        detail="Use Content-Type: application/json or multipart/form-data.",
    )


@router.get("", response_model=SuccessResponse[List[ClassResponse]])
async def get_my_classes(
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List classes (role-based access).
    - Teachers: Returns only assigned classes
    - Admins: Returns all classes in the school
    """
    from app.models.enums import UserRole

    if current_user.role == UserRole.SCHOOL_ADMIN:
        # Admin: get all school classes
        classes = await AcademicService.get_school_classes(db, current_user.school_id)
    else:
        # Teacher: get only assigned classes
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


@router.post("", response_model=SuccessResponse[Any])
async def create_class(
    parsed: Tuple[ClassCreate, Optional[bytes]] = Depends(parse_create_class_request),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create new class. Accepts application/json (ClassCreate) or multipart/form-data
    with required 'data' (class JSON) and optional 'file' (CSV roster). If file is
    provided, students are created/enrolled from the CSV after the class is created.

    **JSON Request Example:**
    ```json
    {
      "name": "French 101",
      "description": "Beginner French class (optional)",
      "timeline": "Spring 2026 (optional)",
      "schedule": [
        {
          "day_of_week": "Mon",
          "start_time": "09:00:00",
          "end_time": "10:00:00"
        }
      ],
      "language_id": 1,
      "term_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    ```

    **Required Fields:**
    - `name`: Class name (string)
    - `schedule`: Array of schedule objects with day_of_week, start_time, end_time
    - `language_id`: Language ID (integer, e.g., 1 for French, 2 for Spanish)
    - `term_id`: Term UUID (get from GET /api/v1/schools/terms)

    **Optional Fields:**
    - `description`: Class description (string)
    - `timeline`: Timeline text (string, e.g., "Jan 2026 - May 2026")
    - `sub_class`: Sub-class name (string)
    - `level`: Proficiency level (string)
    - `classroom_id`: Physical classroom UUID (optional)
    - `status`: "active" | "inactive" | "archived" (defaults to "active")

    **Multipart Form-Data Alternative (for CSV roster upload):**
    - `data`: JSON string with class data (same structure as above)
    - `file`: CSV file with columns: first_name, last_name, email

    **Day of Week Values:** "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"

    **Time Format:** "HH:MM:SS" (24-hour format, e.g., "09:00:00", "14:30:00")
    """
    class_in, roster_file = parsed
    try:
        new_class = await AcademicService.create_class(
            db,
            current_user.school_id,
            class_in,
            teacher_id=current_user.id,
        )
    except IntegrityError:
        raise HTTPException(status_code=400, detail="Invalid data provided, e.g., nonexistent term_id or language_id.")

    data: Any = ClassResponse.model_validate(new_class).model_dump()
    if roster_file is not None:
        result = await AcademicService.import_roster_from_csv(
            db,
            new_class.id,
            roster_file,
            current_user.school_id,
            new_class.language_id,
        )
        data["roster_import"] = result
    return SuccessResponse(data=data, message="Class created successfully")


@router.get("/monitor/stats", response_model=SuccessResponse[RoomMonitorStats])
async def get_room_monitor_stats(
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
    timeframe: str = Query("week", description="week | month | all"),
) -> Any:
    """
    Room monitor KPI stats (Figma: Total Learning Sessions, Active Students, Avg. Session Duration).
    """
    if timeframe not in VALID_LEADERBOARD_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe must be one of: {', '.join(sorted(VALID_LEADERBOARD_TIMEFRAMES))}",
        )
    total_sessions, active_students, avg_mins = await LearningSessionService.get_monitor_stats(
        db, current_user, timeframe
    )
    data = RoomMonitorStats(
        total_sessions=total_sessions,
        active_students=active_students,
        avg_session_duration_minutes=avg_mins,
    )
    return SuccessResponse(data=data, message="Room monitor stats retrieved successfully")


@router.get("/monitor/summary", response_model=SuccessResponse[List[ClassPerformanceSummaryRow]])
async def get_room_monitor_summary(
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Class Performance Summary table (Figma: Class Name, Module Progress, Avg. Quiz Score, Time Spent, Last Activity).
    """
    rows_data = await LearningSessionService.list_class_performance_summary_rows(
        db, current_user
    )
    data = [
        ClassPerformanceSummaryRow(
            class_id=row["class_id"],
            class_name=row["class_name"],
            student_count=row["student_count"],
            module_progress_pct=row["module_progress_pct"],
            module_progress_label=row["module_progress_label"],
            avg_quiz_score_pct=row["avg_quiz_score_pct"],
            time_spent_minutes_per_student=row["time_spent_minutes_per_student"],
            last_activity_at=row["last_activity_at"],
            active_session=LearningSessionOut.model_validate(active) if active else None,
        )
        for active, row in rows_data
    ]
    return SuccessResponse(data=data, message="Class performance summary retrieved successfully")


@router.get("/monitor", response_model=SuccessResponse[List[RoomMonitorCard]])
async def list_room_monitor_cards(
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Room monitor dashboard: one card per class the user has access to (Figma: row of class cards).
    """
    cards_data = await LearningSessionService.list_monitor_cards_for_teacher(db, current_user)
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
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Room monitor detail for one class: card data plus Class Performance Summary (Figma: detail + summary section).
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    # Check if user has access to this class
    has_access = await LearningSessionService._user_has_class_access(db, current_user, class_id)
    if not has_access:
        raise HTTPException(status_code=404, detail="Class not found")

    roster = await AcademicService.get_class_roster(db, class_id)
    active = await LearningSessionService.get_active_session(db, class_id)
    recent_sessions = await LearningSessionService.list_sessions_for_class(
        db, class_id, current_user, limit=5
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
    current_user: User = Depends(deps.require_teacher_or_admin),
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
        db, class_id, current_user, limit=limit
    )
    return SuccessResponse(
        data=[LearningSessionOut.model_validate(s) for s in sessions],
        message="Sessions retrieved successfully",
    )


@router.post("/{class_id}/sessions", response_model=SuccessResponse[LearningSessionOut])
async def start_class_session(
    class_id: UUID,
    body: LearningSessionCreate,
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Start a learning session for the class. Only one active session per class at a time.
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    session = await LearningSessionService.start_session(
        db, class_id, current_user, body.session_type
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
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    End an in-progress learning session.
    """
    cls = await AcademicService.get_class_by_id(db, class_id)
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    ok = await LearningSessionService.end_session(db, session_id, class_id, current_user)
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
