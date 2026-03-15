"""
Arena management endpoints — teacher console only.
All routes require teacher auth and operate on arenas for classes the teacher teaches.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.models.enums import ArenaStatus
from app.schemas.communication import (
    ArenaCreate,
    ArenaUpdate,
    ArenaResponse,
    ArenaListRow,
    # Phase 1: Session configuration
    StudentSearchResponse,
    StudentListItem,
    ArenaInitializeRequest,
    ArenaInitializeResponse,
    ArenaSessionConfig,
    RandomizeStudentsRequest,
    RandomizeStudentsResponse,
    HybridSelectionRequest,
    HybridSelectionResponse,
)
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services.arena_service import ArenaService

router = APIRouter()


def _arena_to_response(arena) -> dict:
    criteria = [{"name": c.name, "weight_percentage": c.weight_percentage} for c in arena.criteria]
    rules = [r.description for r in arena.rules]
    return {
        "id": arena.id,
        "class_id": arena.class_id,
        "title": arena.title,
        "description": arena.description,
        "status": arena.status,
        "start_time": arena.start_time,
        "duration_minutes": arena.duration_minutes,
        "criteria": criteria,
        "rules": rules,
    }


@router.get("", response_model=PaginatedResponse[ArenaListRow])
async def list_arenas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    status: Optional[ArenaStatus] = Query(None, description="Filter by status"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List arenas for the teacher's classes (Arena list / dashboard)."""
    skip = (page - 1) * page_size
    rows, total = await ArenaService.list_arenas(
        db, current_user.id, class_id=class_id, status=status, skip=skip, limit=page_size
    )
    items = [
        ArenaListRow(
            id=a.id,
            title=a.title,
            status=a.status,
            class_id=a.class_id,
            class_name=class_name,
            start_time=a.start_time,
            duration_minutes=a.duration_minutes,
        )
        for a, class_name in rows
    ]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.post("", response_model=SuccessResponse[ArenaResponse])
async def create_arena(
    body: ArenaCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create an arena for a class the teacher teaches. Teacher is added as moderator."""
    arena = await ArenaService.create_arena(db, current_user.id, body)
    if not arena:
        raise HTTPException(status_code=403, detail="You do not teach this class")
    # Reload with criteria/rules for response
    arena = await ArenaService.get_arena(db, arena.id, current_user.id)
    return SuccessResponse(
        data=ArenaResponse(**_arena_to_response(arena)),
        message="Arena created successfully",
    )


@router.get("/{arena_id}", response_model=SuccessResponse[ArenaResponse])
async def get_arena(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get arena by id (teacher must teach the arena's class)."""
    arena = await ArenaService.get_arena(db, arena_id, current_user.id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    return SuccessResponse(data=ArenaResponse(**_arena_to_response(arena)))


@router.patch("/{arena_id}", response_model=SuccessResponse[ArenaResponse])
async def update_arena(
    arena_id: UUID,
    body: ArenaUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Update arena (teacher must teach the arena's class)."""
    arena = await ArenaService.update_arena(db, arena_id, current_user.id, body)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
    arena = await ArenaService.get_arena(db, arena_id, current_user.id)
    return SuccessResponse(
        data=ArenaResponse(**_arena_to_response(arena)),
        message="Arena updated successfully",
    )


# --- Phase 1: Session Configuration Endpoints ---


@router.get("/students/search", response_model=SuccessResponse[StudentSearchResponse])
async def search_students(
    class_id: UUID = Query(..., description="Class ID to search within"),
    name: Optional[str] = Query(None, description="Search by student name (partial match)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Search for students in a class by name.
    Used by: Student Selection screen (manual/hybrid/randomize tabs)
    """
    # Verify teacher teaches this class
    teaches = await ArenaService._teacher_teaches_class(db, current_user.id, class_id)
    if not teaches:
        raise HTTPException(status_code=403, detail="You do not teach this class")

    skip = (page - 1) * page_size
    students, total = await ArenaService.search_students(
        db, class_id=class_id, name=name, skip=skip, limit=page_size
    )

    student_items = [
        StudentListItem(
            id=s.id,
            name=s.name,
            avatar_url=s.profile_pic_url,
            status="active"
        )
        for s in students
    ]

    return SuccessResponse(
        data=StudentSearchResponse(
            students=student_items,
            total=total,
            page=page,
            page_size=page_size
        )
    )


@router.post("/{arena_id}/initialize", response_model=SuccessResponse[ArenaInitializeResponse])
async def initialize_arena_session(
    arena_id: UUID,
    body: ArenaInitializeRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Initialize arena session with configuration and selected participants.

    Sets arena_mode, judging_mode, AI co-judge, and student selection.
    Updates session_state to 'initialized'.

    Used by: "Begin Arena" button on Student Selection screen
    """
    arena = await ArenaService.initialize_arena_session(
        db, arena_id, current_user.id, body
    )

    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    # Get selected students for response
    participants = []
    if body.selected_student_ids:
        from sqlalchemy import select
        from app.models.user import User as UserModel
        result = await db.execute(
            select(UserModel).where(UserModel.id.in_(body.selected_student_ids))
        )
        users = result.scalars().all()
        participants = [
            StudentListItem(
                id=u.id,
                name=u.name,
                avatar_url=u.profile_pic_url,
                status="active"
            )
            for u in users
        ]

    config = ArenaSessionConfig(
        arena_mode=arena.arena_mode,
        judging_mode=arena.judging_mode,
        ai_co_judge_enabled=arena.ai_co_judge_enabled,
        student_selection_mode=arena.student_selection_mode,
        selected_student_ids=body.selected_student_ids,
        team_size=arena.team_size
    )

    return SuccessResponse(
        data=ArenaInitializeResponse(
            session_id=arena.id,
            status="initialized",
            participants=participants,
            configuration=config
        ),
        message="Arena session initialized successfully"
    )


@router.post("/{arena_id}/students/randomize", response_model=SuccessResponse[RandomizeStudentsResponse])
async def randomize_student_selection(
    arena_id: UUID,
    body: RandomizeStudentsRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Randomly select N students from a class.

    Used by: "Randomize" tab in Student Selection screen
    Returns selected students but does NOT save them (that happens in /initialize)
    """
    # Verify teacher has access to this arena
    arena = await ArenaService.get_arena(db, arena_id, current_user.id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    # Verify teacher teaches the class
    teaches = await ArenaService._teacher_teaches_class(db, current_user.id, body.class_id)
    if not teaches:
        raise HTTPException(status_code=403, detail="You do not teach this class")

    students = await ArenaService.randomize_student_selection(
        db, body.class_id, body.participant_count
    )

    student_items = [
        StudentListItem(
            id=s.id,
            name=s.name,
            avatar_url=s.profile_pic_url,
            status="active"
        )
        for s in students
    ]

    return SuccessResponse(
        data=RandomizeStudentsResponse(selected_students=student_items),
        message=f"Randomly selected {len(student_items)} students"
    )


@router.post("/{arena_id}/students/hybrid", response_model=SuccessResponse[HybridSelectionResponse])
async def hybrid_student_selection(
    arena_id: UUID,
    body: HybridSelectionRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Combine manual student selections with random selections.

    Used by: "Hybrid" tab in Student Selection screen
    Returns combined list but does NOT save (that happens in /initialize)
    """
    # Verify teacher has access to this arena
    arena = await ArenaService.get_arena(db, arena_id, current_user.id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    # Verify teacher teaches the class
    teaches = await ArenaService._teacher_teaches_class(db, current_user.id, body.class_id)
    if not teaches:
        raise HTTPException(status_code=403, detail="You do not teach this class")

    students = await ArenaService.hybrid_student_selection(
        db, body.class_id, body.manual_selections, body.randomize_count
    )

    student_items = [
        StudentListItem(
            id=s.id,
            name=s.name,
            avatar_url=s.profile_pic_url,
            status="active"
        )
        for s in students
    ]

    return SuccessResponse(
        data=HybridSelectionResponse(final_participants=student_items),
        message=f"Selected {len(student_items)} students ({len(body.manual_selections)} manual + {body.randomize_count} random)"
    )
