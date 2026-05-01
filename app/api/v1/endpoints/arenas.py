"""
Arena management endpoints — teacher console only.
All routes require teacher auth and operate on arenas for classes the teacher teaches.
"""

from typing import Any, Optional
import json

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime

from app.config import settings
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
    # Phase 2: Waiting room & admission
    JoinCodeGenerateResponse,
    WaitingRoomJoinRequest,
    WaitingRoomJoinResponse,
    WaitingRoomListResponse,
    WaitingRoomEntry,
    WaitingRoomAdmitResponse,
    WaitingRoomRejectRequest,
    # Phase 3: WebSocket & Live Sessions
    ArenaSessionStateResponse,
    ArenaSessionStartRequest,
    ArenaSessionEndRequest,
    WSClientEvent,
    WSServerEvent,
    # Audio Conferencing
    AudioTokenResponse,
    # Phase 4: Evaluation & Publishing
    ParticipantScoreCard,
    ArenaScoresResponse,
    ArenaSummaryResponse,
    ParticipantAnalytics,
    ArenaAnalyticsResponse,
    TeacherRatingRequest,
    TeacherRatingResponse,
    PublishArenaRequest,
    PublishArenaResponse,
    # Phase 5: Challenge Pool
    ChallengePoolListItem,
    ChallengePoolResponse,
    ChallengePoolDetailResponse,
    PublishToChallengePoolRequest,
    PublishToChallengePoolResponse,
    CloneChallengeRequest,
    CloneChallengeResponse,
    # Phase 6: Collaborative Mode Teams
    CreateTeamRequest,
    CreateTeamResponse,
    BatchCreateTeamRequest,
    BatchCreateTeamResponse,
    ListTeamsResponse,
    ArenaHistoryItem,
    ArenaHistoryResponse,
)
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services.arena_service import ArenaService
from app.services.audio_analysis_service import audio_analysis_service
from app.services.cloudflare_realtimekit_service import realtimekit_service
from app.websocket.arena_connection_manager import connection_manager
from app.core.logging import get_logger

# Set broadcast callback once at module load — no per-connection override needed.
async def _global_broadcast_analysis(arena_id, data: dict):
    await connection_manager.broadcast(arena_id, data)

audio_analysis_service.set_broadcast_callback(_global_broadcast_analysis)

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
    current_user: User = Depends(deps.require_teacher_or_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create an arena for a class the teacher/admin teaches. Teacher/Admin is added as moderator."""
    arena = await ArenaService.create_arena(db, current_user.id, body)
    if not arena:
        raise HTTPException(status_code=403, detail="You do not teach this class")
    # Reload with criteria/rules for response
    arena = await ArenaService.get_arena(db, arena.id, current_user.id)
    return SuccessResponse(
        data=ArenaResponse(**_arena_to_response(arena)),
        message="Arena created successfully",
    )


@router.get("/history", response_model=SuccessResponse[ArenaHistoryResponse])
async def get_history(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[ArenaStatus] = Query(None, description="Filter by arena status"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get historical arenas for the current teacher.
    """
    skip = (page - 1) * page_size
    rows, total = await ArenaService.list_history(
        db=db,
        teacher_id=current_user.id,
        skip=skip,
        limit=page_size,
        status_filter=status
    )
    from app.schemas.communication import ArenaHistoryItem
    history_items = [
        ArenaHistoryItem(
            id=arena.id,
            title=arena.title,
            class_name=class_name,
            status=arena.status,
            session_state=arena.session_state,
            start_time=arena.start_time,
            duration_minutes=arena.duration_minutes,
            arena_mode=arena.arena_mode,
            participant_count=participant_count,
            published_at=arena.published_at
        )
        for arena, class_name, participant_count in rows
    ]
    return SuccessResponse(
        data=ArenaHistoryResponse(
            arenas=history_items,
            total=total,
            page=page,
            page_size=page_size
        ),
        message=f"Retrieved {len(history_items)} of {total} historical arenas"
    )


@router.get("/pool", response_model=SuccessResponse[ChallengePoolResponse])
async def list_challenge_pool(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    arena_mode: Optional[str] = Query(None),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Browse public challenges from the challenge pool.

    Searchable and filterable catalog of reusable arena challenges.

    **Teacher only** - accessible to all teachers.

    Query Parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20, max: 100)
    - search: Search in title and description
    - arena_mode: Filter by mode (competitive/collaborative)

    Used by: Challenge pool browser UI
    """
    skip = (page - 1) * page_size

    challenges, total = await ArenaService.list_challenge_pool(
        db=db,
        skip=skip,
        limit=page_size,
        search=search,
        arena_mode=arena_mode
    )

    # Build response items
    pool_items = []
    for arena, publisher_name in challenges:
        pool_items.append(
            ChallengePoolListItem(
                id=arena.id,
                title=arena.title,
                description=arena.description,
                duration_minutes=arena.duration_minutes,
                arena_mode=arena.arena_mode,
                judging_mode=arena.judging_mode,
                criteria=[
                    {"name": c.name, "weight_percentage": c.weight_percentage}
                    for c in arena.criteria
                ],
                rules=[r.description for r in arena.rules],
                usage_count=arena.usage_count,
                published_at=arena.published_at,
                published_by_name=publisher_name
            )
        )

    return SuccessResponse(
        data=ChallengePoolResponse(
            challenges=pool_items,
            total=total,
            page=page,
            page_size=page_size
        ),
        message="Challenge pool retrieved successfully"
    )


@router.get("/pool/{pool_arena_id}", response_model=SuccessResponse[ChallengePoolDetailResponse])
async def get_challenge_pool_detail(
    pool_arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get detailed information about a specific challenge from the pool.

    **Teacher only** - accessible to all teachers.

    Used by: Challenge preview before cloning
    """
    pool_item = await ArenaService.get_challenge_pool_item(db, pool_arena_id)

    if not pool_item:
        raise HTTPException(status_code=404, detail="Challenge not found in pool")

    arena, publisher_name = pool_item

    return SuccessResponse(
        data=ChallengePoolDetailResponse(
            id=arena.id,
            title=arena.title,
            description=arena.description,
            duration_minutes=arena.duration_minutes,
            arena_mode=arena.arena_mode,
            judging_mode=arena.judging_mode,
            ai_co_judge_enabled=arena.ai_co_judge_enabled,
            team_size=arena.team_size,
            criteria=[
                {"name": c.name, "weight_percentage": c.weight_percentage}
                for c in arena.criteria
            ],
            rules=[r.description for r in arena.rules],
            usage_count=arena.usage_count,
            published_at=arena.published_at,
            published_by_name=publisher_name
        ),
        message="Challenge details retrieved successfully"
    )



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
            name=f"{s.first_name} {s.last_name}",
            avatar_url=s.profile_picture_url,
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
                name=f"{u.first_name} {u.last_name}",
                avatar_url=u.profile_picture_url,
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
    # Verify arena exists (any teacher can check this)
    arena = await ArenaService.get_arena_by_id(db, arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    # Verify teacher teaches the class (returns 403 if not)
    teaches = await ArenaService._teacher_teaches_class(db, current_user.id, body.class_id)
    if not teaches:
        raise HTTPException(status_code=403, detail="You do not teach this class")

    students = await ArenaService.randomize_student_selection(
        db, body.class_id, body.participant_count
    )

    student_items = [
        StudentListItem(
            id=s.id,
            name=f"{s.first_name} {s.last_name}",
            avatar_url=s.profile_picture_url,
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
    # Verify arena exists (any teacher can check this)
    arena = await ArenaService.get_arena_by_id(db, arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")

    # Verify teacher teaches the class (returns 403 if not)
    teaches = await ArenaService._teacher_teaches_class(db, current_user.id, body.class_id)
    if not teaches:
        raise HTTPException(status_code=403, detail="You do not teach this class")

    students = await ArenaService.hybrid_student_selection(
        db, body.class_id, body.manual_selections, body.randomize_count
    )

    student_items = [
        StudentListItem(
            id=s.id,
            name=f"{s.first_name} {s.last_name}",
            avatar_url=s.profile_picture_url,
            status="active"
        )
        for s in students
    ]

    return SuccessResponse(
        data=HybridSelectionResponse(final_participants=student_items),
        message=f"Selected {len(student_items)} students ({len(body.manual_selections)} manual + {body.randomize_count} random)"
    )


# --- Phase 2: Waiting Room & Admission Endpoints ---


@router.post("/{arena_id}/join-code", response_model=SuccessResponse[JoinCodeGenerateResponse])
async def generate_join_code(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Generate join code and QR code for arena.

    Students use this code to join the waiting room.
    Used by: Teacher clicks "Generate Join Code" on Arena Entry screen
    """
    result = await ArenaService.generate_join_code(db, arena_id, current_user.id)

    if not result:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    join_code, qr_code_url, expires_at = result

    return SuccessResponse(
        data=JoinCodeGenerateResponse(
            join_code=join_code,
            qr_code_url=qr_code_url,
            expires_at=expires_at
        ),
        message="Join code generated successfully"
    )


@router.post("/{arena_id}/waiting-room/join", response_model=SuccessResponse[WaitingRoomJoinResponse])
async def join_waiting_room(
    arena_id: UUID,
    body: WaitingRoomJoinRequest,
    current_user: User = Depends(deps.require_student),  # Student auth
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Student joins arena waiting room using join code.

    Used by: Student submits join code on join screen
    """
    entry = await ArenaService.student_join_waiting_room(
        db, arena_id, current_user.id, body.join_code
    )

    if not entry:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired join code, or you have already joined"
        )

    # Calculate position in queue
    from sqlalchemy import select, func
    from app.models.arena import ArenaWaitingRoom
    position_result = await db.execute(
        select(func.count())
        .where(
            ArenaWaitingRoom.arena_id == arena_id,
            ArenaWaitingRoom.status == 'pending',
            ArenaWaitingRoom.entry_timestamp <= entry.entry_timestamp
        )
    )
    position = position_result.scalar() or 1

    return SuccessResponse(
        data=WaitingRoomJoinResponse(
            waiting_room_id=entry.id,
            status="pending",
            position_in_queue=position
        ),
        message="Successfully joined waiting room"
    )


@router.get("/{arena_id}/waiting-room", response_model=SuccessResponse[WaitingRoomListResponse])
async def list_waiting_room(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    List students in arena waiting room.

    Used by: Teacher sees pending students list on Arena Entry screen
    """
    result = await ArenaService.list_waiting_room(db, arena_id, current_user.id)

    if result is None:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    pending_entries, total_pending, total_admitted, total_rejected = result

    entries = [
        WaitingRoomEntry(
            entry_id=entry.id,
            student_id=user.id,
            student_name=f"{user.first_name} {user.last_name}",
            avatar_url=user.profile_picture_url,
            entry_timestamp=entry.entry_timestamp,
            status=entry.status
        )
        for entry, user in pending_entries
    ]

    return SuccessResponse(
        data=WaitingRoomListResponse(
            pending_students=entries,
            total_pending=total_pending,
            total_admitted=total_admitted,
            total_rejected=total_rejected
        )
    )


@router.post("/{arena_id}/waiting-room/{entry_id}/admit", response_model=SuccessResponse[WaitingRoomAdmitResponse])
async def admit_student(
    arena_id: UUID,
    entry_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Admit student from waiting room to arena.

    Used by: Teacher clicks "Admit" button on waiting room entry
    """
    entry = await ArenaService.admit_student(db, arena_id, entry_id, current_user.id)

    if not entry:
        raise HTTPException(status_code=404, detail="Waiting room entry not found or already processed")

    # Look up the ArenaParticipant created during admission
    from app.models.arena import ArenaParticipant as AP
    part_result = await db.execute(
        select(AP).where(AP.arena_id == arena_id, AP.student_id == entry.student_id)
    )
    participant = part_result.scalar_one_or_none()

    return SuccessResponse(
        data=WaitingRoomAdmitResponse(
            success=True,
            participant_id=participant.id if participant else entry.student_id,
        ),
        message="Student admitted successfully"
    )


@router.post("/{arena_id}/waiting-room/{entry_id}/reject", response_model=SuccessResponse[WaitingRoomAdmitResponse])
async def reject_student(
    arena_id: UUID,
    entry_id: UUID,
    body: WaitingRoomRejectRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Reject student from waiting room.

    Used by: Teacher clicks "Reject" button on waiting room entry
    """
    entry = await ArenaService.reject_student(
        db, arena_id, entry_id, current_user.id, body.reason
    )

    if not entry:
        raise HTTPException(status_code=404, detail="Waiting room entry not found or already processed")

    return SuccessResponse(
        data=WaitingRoomAdmitResponse(success=True, participant_id=None),
        message="Student rejected successfully"
    )


# ============================================================================
# Phase 3: WebSocket & Live Session Management
# ============================================================================


@router.post("/{arena_id}/audio/token", response_model=SuccessResponse[AudioTokenResponse])
async def generate_audio_token(
    arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Generate Cloudflare RealtimeKit audio token for arena session.

    Flow:
    1. Get or create RealtimeKit meeting for this arena
    2. Add user as participant to meeting
    3. Return authToken from Cloudflare for frontend SDK

    Teachers/Admins use "group_call_host" preset (can publish audio + moderate).
    Students use "group_call_participant" preset (can publish audio + listen).

    **Authentication required** - teacher or admitted student.

    Used by: Audio join flow before WebSocket connection
    """
    logger = get_logger(__name__)

    # Verify arena exists — use get_arena_by_id (no teacher join) so both teachers
    # and admitted students can reach this endpoint.
    arena = await ArenaService.get_arena_by_id(db, arena_id)
    if not arena:
        logger.warning("audio_token_denied_arena_not_found", extra={"arena_id": str(arena_id)})
        raise HTTPException(status_code=404, detail="Arena not found")

    # Verify arena session is live or initialized
    if arena.session_state not in ["initialized", "live"]:
        logger.warning("audio_token_denied_session_not_active", extra={
            "arena_id": str(arena_id),
            "session_state": arena.session_state
        })
        raise HTTPException(status_code=400, detail="Arena session is not active")

    # Role-based authorization
    from app.models.enums import UserRole
    is_teacher = current_user.role in [UserRole.TEACHER, UserRole.SCHOOL_ADMIN]

    if is_teacher:
        preset_name = "group_call_host"
    else:
        # Verify student was admitted from waiting room
        is_admitted = await ArenaService.is_arena_participant(db, arena_id, current_user.id)
        if not is_admitted:
            logger.warning("audio_token_denied_not_participant", extra={
                "arena_id": str(arena_id),
                "user_id": str(current_user.id)
            })
            raise HTTPException(status_code=403, detail="Not authorized for this arena")
        preset_name = "group_call_participant"

    # Get or create RealtimeKit meeting
    meeting_data = await realtimekit_service.get_or_create_meeting(
        arena_id=arena_id,
        arena_title=arena.title,
        existing_meeting_id=arena.realtimekit_meeting_id
    )

    if not meeting_data:
        logger.error("failed_to_create_meeting", extra={"arena_id": str(arena_id)})
        raise HTTPException(status_code=500, detail="Failed to create audio meeting")

    meeting_id = meeting_data["id"]

    # Save meeting ID to arena if new
    if not arena.realtimekit_meeting_id:
        arena.realtimekit_meeting_id = meeting_id
        await db.commit()
        logger.info("meeting_created_and_saved", extra={
            "arena_id": str(arena_id),
            "meeting_id": meeting_id
        })

    # Add user as participant to meeting
    user_name = f"{current_user.first_name} {current_user.last_name}"
    participant_data = await realtimekit_service.add_participant(
        meeting_id=meeting_id,
        user_id=current_user.id,
        user_name=user_name,
        preset_name=preset_name
    )

    if not participant_data:
        logger.error("failed_to_add_participant", extra={
            "arena_id": str(arena_id),
            "user_id": str(current_user.id)
        })
        raise HTTPException(status_code=500, detail="Failed to add participant to meeting")

    logger.info("audio_token_generated", extra={
        "arena_id": str(arena_id),
        "user_id": str(current_user.id),
        "preset": preset_name,
        "meeting_id": meeting_id
    })

    return SuccessResponse(
        data=AudioTokenResponse(
            token=participant_data["token"],
            participant_id=participant_data["id"],
            meeting_id=meeting_id,
            preset_name=preset_name,
            name=user_name
        ),
        message=f"Audio token generated ({preset_name})"
    )


@router.websocket("/{arena_id}/live")
async def arena_live_session(
    websocket: WebSocket,
    arena_id: UUID,
    db: AsyncSession = Depends(deps.get_db),
):
    """
    WebSocket endpoint for real-time arena session coordination.

    Client connects after being admitted to waiting room or as teacher.
    Receives: speaking updates, engagement metrics, reactions, session events
    Sends: speaking events, reactions

    Note: Audio transmission is handled separately by Cloudflare RealtimeKit (WebRTC).
    This WebSocket is for session coordination and metadata only.

    Architecture: Uses Redis Pub/Sub for horizontal scaling across multiple servers.

    Authentication: Token in query param (?token=JWT) or Authorization header
    """
    logger = get_logger(__name__)

    # Authenticate WebSocket connection
    user = await deps.authenticate_websocket(websocket, db)
    if not user:
        return  # authenticate_websocket already closed connection

    user_id = user.id
    correlation_id = f"ws-{arena_id}-{user_id}"

    log = get_logger(__name__)

    log.info("websocket_connection_attempt")

    # Verify arena exists + role-based access path.
    # IMPORTANT: ArenaService.get_arena() is teacher-scoped (joins teacher_assignments),
    # so using it for students incorrectly returns None and denies valid admitted users.
    from app.models.enums import UserRole
    is_teacher = user.role in [UserRole.TEACHER, UserRole.SCHOOL_ADMIN]
    arena = (
        await ArenaService.get_arena(db, arena_id, user_id)
        if is_teacher
        else await ArenaService.get_arena_by_id(db, arena_id)
    )
    if not arena:
        log.warning("websocket_denied_arena_not_found")
        await websocket.close(code=4004, reason="Arena not found or access denied")
        return

    # Verify arena session is live or initialized (teacher opens monitoring before pressing Begin)
    if arena.session_state not in ("live", "initialized"):
        log.warning("websocket_denied_arena_not_live")
        await websocket.close(code=4003, reason="Arena session not live")
        return

    # Authorization: Verify user is teacher or admitted participant
    if not is_teacher:
        # Verify student was admitted from waiting room
        is_admitted = await ArenaService.is_arena_participant(db, arena_id, user_id)
        if not is_admitted:
            log.warning("websocket_denied_not_participant")
            await websocket.close(code=4003, reason="Not authorized for this arena")
            return

    log.info("websocket_authorization_granted")

    # Connect to WebSocket manager
    await connection_manager.connect(arena_id, user_id, websocket)
    log.info("websocket_connected")

    try:
        # Send initial session state
        participants = await ArenaService.get_arena_participants(db, arena_id)
        await connection_manager.send_personal_message(
            arena_id,
            user_id,
            {
                "event_type": "session_state",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "arena_id": str(arena_id),
                    "session_state": arena.session_state,
                    "active_speaker_id": None,  # Tracked client-side via Cloudflare RealtimeKit
                    "participants": participants,
                },
            },
        )

        log.info("websocket_initial_state_sent")

        # Initialize audio analysis session if participant (not audience)
        # Resolve arena language: arena -> class -> language -> code
        _analysis_session_started = False
        if not is_teacher:
            try:
                from app.models.academic import Class
                from app.models.onboarding import Language
                class_result = await db.execute(
                    select(Language.code).join(Class, Class.language_id == Language.id).where(Class.id == arena.class_id)
                )
                lang_code = class_result.scalar_one_or_none() or "en"
                student_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "Student"
                _analysis_session_started = await audio_analysis_service.start_session(
                    arena_id, user_id, lang_code, student_name
                )
                if _analysis_session_started:
                    log.info("audio_analysis_session_initialized", extra={"lang": lang_code})
                else:
                    from app.config import settings as _settings
                    if not _settings.AZURE_SPEECH_KEY:
                        log.warning(
                            "audio_analysis_disabled_no_azure_key",
                            extra={"hint": "Set AZURE_SPEECH_KEY env var to enable pronunciation feedback"},
                        )
                    else:
                        log.warning("audio_analysis_session_start_failed_unknown")
            except Exception as e:
                log.warning("audio_analysis_init_failed", extra={"error": str(e)})

        # Message counter for rate limiting (text messages only)
        message_count = 0
        message_window_start = datetime.utcnow()

        # Byte rate limiting for audio: 512KB per second
        audio_bytes_count = 0
        audio_window_start = datetime.utcnow()
        AUDIO_BYTE_RATE_LIMIT = 512 * 1024  # 512KB/s

        # Listen for client events (text and binary frames)
        while True:
            ws_message = await websocket.receive()

            # Handle binary frames (audio chunks)
            if "bytes" in ws_message and ws_message["bytes"] is not None:
                audio_data = ws_message["bytes"]

                # Audio byte rate limiting
                now = datetime.utcnow()
                elapsed = (now - audio_window_start).total_seconds()
                if elapsed >= 1.0:
                    audio_bytes_count = len(audio_data)
                    audio_window_start = now
                else:
                    audio_bytes_count += len(audio_data)
                    if audio_bytes_count > AUDIO_BYTE_RATE_LIMIT:
                        log.warning("audio_byte_rate_limit_exceeded")
                        continue  # Drop chunk, don't disconnect

                # Feed to analysis service (students only). Teacher monitoring streams their
                # own mic tap here but Azure sessions are not started for teachers — analysis
                # runs on each student's /live connection so broadcasts reach the teacher UI.
                if _analysis_session_started:
                    await audio_analysis_service.process_audio_chunk(arena_id, user_id, audio_data)
                continue

            # Handle text frames (JSON events)
            if "text" not in ws_message or ws_message["text"] is None:
                continue

            data = ws_message["text"]

            # Rate limiting: 30 messages per minute per user
            message_count += 1
            now = datetime.utcnow()
            elapsed = (now - message_window_start).total_seconds()

            if elapsed >= 60:
                # Reset window
                message_count = 1
                message_window_start = now
            elif message_count > 30:
                log.warning("websocket_rate_limit_exceeded")
                await websocket.close(code=4008, reason="Rate limit exceeded")
                return

            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                log.warning("websocket_invalid_json")
                continue

            event_type = message.get("event_type")
            log.debug("websocket_message_received")

            if event_type == "speaking_started":
                # Broadcast to all participants
                await connection_manager.broadcast(
                    arena_id,
                    {
                        "event_type": "speaking_update",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "user_id": str(user_id),
                            "is_speaking": True,
                        },
                    },
                )
                log.debug("websocket_speaking_started_broadcasted")

            elif event_type == "speaking_stopped":
                await connection_manager.broadcast(
                    arena_id,
                    {
                        "event_type": "speaking_update",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "user_id": str(user_id),
                            "is_speaking": False,
                        },
                    },
                )
                log.debug("websocket_speaking_stopped_broadcasted")

            else:
                log.warning("websocket_unknown_event_type")

    except WebSocketDisconnect:
        log.info("websocket_disconnected_by_client")
    except Exception as e:
        log.error("websocket_error")
    finally:
        # Clean up audio analysis session and persist final scores
        if _analysis_session_started:
            final_result = await audio_analysis_service.close_session(arena_id, user_id)
            if final_result and (final_result.accuracy_score > 0 or final_result.fluency_score > 0):
                log.info(
                    "audio_analysis_final_scores",
                    extra={
                        "accuracy": final_result.accuracy_score,
                        "fluency": final_result.fluency_score,
                    },
                )
                # Persist scores to DB
                try:
                    from app.models.arena import ArenaParticipant
                    result = await db.execute(
                        select(ArenaParticipant).where(
                            ArenaParticipant.arena_id == arena_id,
                            ArenaParticipant.student_id == user_id,
                        )
                    )
                    participant = result.scalar_one_or_none()
                    if participant:
                        participant.ai_pronunciation_score = round(final_result.pronunciation_score, 2)
                        participant.ai_fluency_score = round(final_result.fluency_score, 2)
                        await db.commit()
                        log.info("audio_analysis_scores_persisted")
                except Exception as e:
                    log.warning("audio_analysis_score_persist_failed", extra={"error": str(e)})
        await connection_manager.disconnect(arena_id, user_id, websocket)
        log.info("websocket_connection_closed")


@router.post("/{arena_id}/start", response_model=SuccessResponse[ArenaSessionStateResponse])
async def start_arena_session(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Start live arena session.

    Transitions session_state from 'initialized' to 'live'.
    Broadcasts session_started event to all connected WebSocket clients.

    Used by: Teacher clicks "Start Session" button
    """
    logger = get_logger(__name__)
    log = get_logger(__name__)

    log.info("arena_session_start_requested")

    # Update arena session state
    arena = await ArenaService.start_arena_session(db, arena_id, current_user.id)

    if not arena:
        log.warning("arena_session_start_denied_not_found")
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    log.info("arena_session_started")

    # Recording auto-starts when first participant joins (record_on_start=True)
    # Mark recording as started
    arena.recording_status = "recording"
    arena.recording_started_at = datetime.utcnow()
    await db.commit()
    log.info("cloud_recording_will_auto_start", extra={
        "meeting_id": arena.realtimekit_meeting_id
    })

    # Broadcast session start to all connected clients
    await connection_manager.broadcast(
        arena_id,
        {
            "event_type": "session_state",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "arena_id": str(arena_id),
                "session_state": "live",
                "message": "Session started",
            },
        },
    )

    log.info("arena_session_start_broadcasted")

    return SuccessResponse(
        data=ArenaSessionStateResponse(
            arena_id=arena.id,
            session_state=arena.session_state,
            start_time=arena.start_time,
            duration_minutes=arena.duration_minutes,
            active_speaker_id=None,
            participants=await ArenaService.get_arena_participants(db, arena.id),
        ),
        message="Arena session started successfully"
    )


@router.post("/{arena_id}/end", response_model=SuccessResponse[ArenaSessionStateResponse])
async def end_arena_session(
    arena_id: UUID,
    body: ArenaSessionEndRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    End live arena session.

    Transitions session_state from 'live' to 'completed' (or 'cancelled' if reason provided).
    Broadcasts session_ended event to all connected WebSocket clients.
    Disconnects all WebSocket connections.

    Used by: Teacher clicks "End Session" button
    """
    logger = get_logger(__name__)
    log = get_logger(__name__)

    log.info("arena_session_end_requested")

    # Update arena session state
    arena = await ArenaService.end_arena_session(
        db, arena_id, current_user.id, reason=body.reason
    )

    if not arena:
        log.warning("arena_session_end_denied_not_found")
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    log.info("arena_session_ended")

    # Recording auto-stops when last participant leaves
    # Mark recording as completed
    if arena.recording_status == "recording":
        arena.recording_status = "completed"
        arena.recording_stopped_at = datetime.utcnow()
        # Transcription is handled client-side via Cloudflare SDK
        await db.commit()
        log.info("cloud_recording_will_auto_stop", extra={
            "meeting_id": arena.realtimekit_meeting_id
        })

    # Broadcast session end to all connected clients
    await connection_manager.broadcast(
        arena_id,
        {
            "event_type": "session_ended",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "arena_id": str(arena_id),
                "reason": body.reason or "Session ended by teacher",
            },
        },
    )

    log.info("arena_session_end_broadcasted")

    # Close all audio analysis sessions for this arena
    await audio_analysis_service.close_all_sessions(arena_id)
    log.info("audio_analysis_sessions_closed")

    # Clients receive the "session_ended" broadcast above and disconnect on their own.

    return SuccessResponse(
        data=ArenaSessionStateResponse(
            arena_id=arena.id,
            session_state=arena.session_state,
            start_time=arena.start_time,
            duration_minutes=arena.duration_minutes,
            active_speaker_id=None,
            participants=[],
        ),
        message="Arena session ended successfully"
    )


@router.get("/{arena_id}/session", response_model=SuccessResponse[ArenaSessionStateResponse])
async def get_arena_session_state(
    arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get current arena session state.

    Returns: session_state, active participants, audience (admitted students),
    and pending waiting room entries.

    Used by: Client polling for session updates (LiveMonitoringPage)
    """
    from app.models.arena import ArenaParticipant, ArenaWaitingRoom
    from app.models.user import User as UserModel
    from app.schemas.communication import AudienceMember

    arena = await ArenaService.get_arena(db, arena_id, current_user.id)

    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    # Get connected users count (local to this server)
    connected_users = connection_manager.get_connected_users(arena_id)

    # Fetch admitted students (audience) from ArenaParticipant table
    participant_rows = (await db.execute(
        select(ArenaParticipant, UserModel)
        .join(UserModel, UserModel.id == ArenaParticipant.student_id)
        .where(ArenaParticipant.arena_id == arena_id)
    )).all()

    audience = [
        AudienceMember(
            id=ap.id,
            student_id=ap.student_id,
            name=f"{u.first_name} {u.last_name}",
            role=ap.role or "audience",
        )
        for ap, u in participant_rows
    ]

    # Fetch pending waiting room entries
    waiting_rows = (await db.execute(
        select(ArenaWaitingRoom, UserModel)
        .join(UserModel, UserModel.id == ArenaWaitingRoom.student_id)
        .where(
            ArenaWaitingRoom.arena_id == arena_id,
            ArenaWaitingRoom.status == "pending",
        )
    )).all()

    waiting_room = [
        {
            "entry_id": str(wr.id),
            "student_id": str(wr.student_id),
            "student_name": f"{u.first_name} {u.last_name}",
            "email": u.email,
            "status": wr.status,
        }
        for wr, u in waiting_rows
    ]

    return SuccessResponse(
        data=ArenaSessionStateResponse(
            arena_id=arena.id,
            session_state=arena.session_state,
            start_time=arena.start_time,
            duration_minutes=arena.duration_minutes,
            active_speaker_id=None,  # Tracked client-side via Cloudflare RealtimeKit
            participants=[
                {"user_id": str(uid), "connected": True}
                for uid in connected_users
            ],
            audience=audience,
            audience_count=len(audience),
            waiting_room=waiting_room,
        ),
        message="Session state retrieved successfully"
    )


# ============================================================================
# Phase 4: Evaluation & Publishing
# ============================================================================


@router.get("/{arena_id}/scores", response_model=SuccessResponse[ArenaScoresResponse])
async def get_arena_scores(
    arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get live scoring data for arena.

    Returns participant scores, speaking time, engagement, reactions.

    **Teacher only** - requires arena ownership.

    Used by: Teacher dashboard during live session
    """
    result = await ArenaService.get_arena_scores(db, arena_id, current_user.id)

    if not result:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    arena, participants_data = result

    # Build score cards
    score_cards = []
    for participant, user, reactions_count in participants_data:
        # Get AI scores: prefer live analysis, fall back to persisted DB values
        live_analysis = audio_analysis_service.get_latest_analysis(arena_id, participant.student_id)
        ai_pron = live_analysis.pronunciation_score if live_analysis else None
        ai_flu = live_analysis.fluency_score if live_analysis else None
        # Fall back to DB if no live session
        if ai_pron is None and participant.ai_pronunciation_score is not None:
            ai_pron = float(participant.ai_pronunciation_score)
        if ai_flu is None and participant.ai_fluency_score is not None:
            ai_flu = float(participant.ai_fluency_score)

        score_cards.append(
            ParticipantScoreCard(
                participant_id=participant.id,
                student_id=participant.student_id,
                student_name=f"{user.first_name} {user.last_name}",
                avatar_url=user.profile_picture_url,
                total_speaking_duration_seconds=participant.total_speaking_duration_seconds,
                engagement_score=float(participant.engagement_score),
                reactions_received=reactions_count,
                ai_pronunciation_score=ai_pron,
                ai_fluency_score=ai_flu,
                teacher_rating=float(participant.teacher_rating) if participant.teacher_rating is not None else None,
            )
        )

    # Determine top performers (top 3 by engagement score)
    top_performers = [card.participant_id for card in sorted(
        score_cards,
        key=lambda x: x.engagement_score,
        reverse=True
    )[:3]]

    return SuccessResponse(
        data=ArenaScoresResponse(
            arena_id=arena_id,
            session_state=arena.session_state,
            participants=score_cards,
            top_performers=top_performers
        ),
        message="Scores retrieved successfully"
    )


@router.get("/{arena_id}/analytics", response_model=SuccessResponse[ArenaAnalyticsResponse])
async def get_arena_analytics(
    arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get detailed analytics for arena session.

    Returns comprehensive analytics including timelines, reaction breakdowns,
    and aggregate statistics.

    **Teacher only** - requires arena ownership.

    Used by: Post-session analytics dashboard
    """
    analytics_data = await ArenaService.get_arena_analytics(db, arena_id, current_user.id)

    if not analytics_data:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    return SuccessResponse(
        data=ArenaAnalyticsResponse(
            arena_id=UUID(analytics_data['arena_id']),
            session_duration_minutes=analytics_data['session_duration_minutes'],
            total_participants=analytics_data['total_participants'],
            participants=[
                ParticipantAnalytics(**p) for p in analytics_data['participants']
            ],
            aggregate_stats=analytics_data['aggregate_stats']
        ),
        message="Analytics retrieved successfully"
    )


@router.get("/{arena_id}/summary", response_model=SuccessResponse[ArenaSummaryResponse])
async def get_arena_summary(
    arena_id: UUID,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Get post-session summary for arena evaluation.

    Returns top 2 participants (A vs B) with average scores,
    total reactions, final judgment, and session duration.

    **Teacher only** - requires arena ownership.

    Used by: FinalEvaluationPage
    """
    summary_data = await ArenaService.get_arena_summary(db, arena_id, current_user.id)

    if not summary_data:
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    return SuccessResponse(
        data=ArenaSummaryResponse(
            arena_id=UUID(summary_data['arena_id']),
            participant_a_id=UUID(summary_data['participant_a_id']) if summary_data['participant_a_id'] else None,
            participant_a_name=summary_data['participant_a_name'],
            participant_a_average_score=summary_data['participant_a_average_score'],
            participant_b_id=UUID(summary_data['participant_b_id']) if summary_data['participant_b_id'] else None,
            participant_b_name=summary_data['participant_b_name'],
            participant_b_average_score=summary_data['participant_b_average_score'],
            total_participants=summary_data['total_participants'],
            total_reactions=summary_data['total_reactions'],
            final_judgment=summary_data['final_judgment'],
            duration_minutes=summary_data['duration_minutes'],
        ),
        message="Arena summary retrieved successfully"
    )


@router.post("/{arena_id}/participants/{participant_id}/rate", response_model=SuccessResponse[TeacherRatingResponse])
async def rate_participant(
    arena_id: UUID,
    participant_id: UUID,
    rating_data: TeacherRatingRequest,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Submit teacher rating for participant.

    Allows teacher to rate participant performance based on defined criteria.

    **Teacher only** - requires arena ownership.

    Used by: Post-session evaluation
    """
    logger = get_logger(__name__)
    correlation_id = f"rate-{arena_id}-{participant_id}"
    log = get_logger(__name__)
    log.info("teacher_rating_submission_started")

    participant = await ArenaService.save_teacher_rating(
        db=db,
        participant_id=participant_id,
        teacher_id=current_user.id,
        overall_rating=rating_data.overall_rating,
        criteria_scores=rating_data.criteria_scores,
        feedback=rating_data.feedback
    )

    if not participant:
        log.warning("teacher_rating_failed")
        raise HTTPException(status_code=404, detail="Participant not found or access denied")

    log.info("teacher_rating_saved")

    return SuccessResponse(
        data=TeacherRatingResponse(
            success=True,
            participant_id=participant_id,
            overall_rating=rating_data.overall_rating
        ),
        message="Rating submitted successfully"
    )


@router.post("/{arena_id}/publish", response_model=SuccessResponse[PublishArenaResponse])
async def publish_arena_results(
    arena_id: UUID,
    publish_data: PublishArenaRequest,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Publish arena results for student viewing.

    Makes session results visible to participants based on visibility settings.
    Optionally triggers AI analysis.

    **Teacher only** - requires arena ownership.

    Used by: Post-session publishing workflow
    """
    logger = get_logger(__name__)
    correlation_id = f"publish-{arena_id}"
    log = get_logger(__name__)
    log.info("arena_publish_started")

    arena = await ArenaService.publish_arena_results(
        db=db,
        arena_id=arena_id,
        teacher_id=current_user.id,
        include_ai_analysis=publish_data.include_ai_analysis,
        visibility=publish_data.visibility
    )

    if not arena:
        log.warning("arena_publish_failed")
        raise HTTPException(status_code=404, detail="Arena not found, not completed, or access denied")

    base = settings.FRONTEND_URL
    if publish_data.visibility == "public":
        share_url = f"{base}/share/arenas/{arena_id}"
    else:
        # class and school visibility require auth; same URL, frontend enforces access
        share_url = f"{base}/arenas/{arena_id}/results"

    log.info("arena_published")

    return SuccessResponse(
        data=PublishArenaResponse(
            success=True,
            arena_id=arena_id,
            published_at=datetime.utcnow(),
            share_url=share_url
        ),
        message="Arena results published successfully"
    )


# ============================================================================
# Phase 5: Challenge Pool
# ============================================================================


@router.post("/{arena_id}/publish-to-pool", response_model=SuccessResponse[PublishToChallengePoolResponse])
async def publish_to_challenge_pool(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Publish arena to public challenge pool.

    Makes your arena available for other teachers to clone and use.
    Only completed arenas can be published.

    **Teacher only** - requires arena ownership.

    Used by: Post-session publishing workflow
    """
    logger = get_logger(__name__)
    log = get_logger(__name__)

    log.info("challenge_pool_publish_started")

    arena = await ArenaService.publish_to_challenge_pool(
        db=db,
        arena_id=arena_id,
        teacher_id=current_user.id
    )

    if not arena:
        log.warning("challenge_pool_publish_failed")
        raise HTTPException(
            status_code=404,
            detail="Arena not found, not completed, or access denied"
        )

    log.info("challenge_pool_published")

    return SuccessResponse(
        data=PublishToChallengePoolResponse(
            success=True,
            arena_id=arena_id,
            published_at=arena.published_at,
            message="Challenge published to pool successfully"
        ),
        message="Challenge published to pool successfully"
    )


@router.post("/pool/{pool_arena_id}/clone", response_model=SuccessResponse[CloneChallengeResponse])
async def clone_challenge_from_pool(
    pool_arena_id: UUID,
    clone_data: CloneChallengeRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Clone a challenge from the pool to your class.

    Creates a copy of the challenge that you can customize and use with your students.
    Increments the usage count on the original challenge.

    **Teacher only** - must teach the target class.

    Used by: Challenge pool browser (clone button)
    """
    logger = get_logger(__name__)
    log = get_logger(__name__)

    log.info("challenge_clone_started")

    cloned_arena = await ArenaService.clone_challenge_from_pool(
        db=db,
        pool_arena_id=pool_arena_id,
        teacher_id=current_user.id,
        class_id=clone_data.class_id,
        customize_title=clone_data.customize_title
    )

    if not cloned_arena:
        log.warning("challenge_clone_failed")
        raise HTTPException(
            status_code=404,
            detail="Challenge not found in pool or you don't have access to the target class"
        )

    log.info("challenge_cloned")

    return SuccessResponse(
        data=CloneChallengeResponse(
            success=True,
            new_arena_id=cloned_arena.id,
            source_arena_id=pool_arena_id,
            message="Challenge cloned successfully"
        ),
        message="Challenge cloned successfully. You can now customize and schedule it."
    )


# =====================================================================
# Phase 6: Collaborative Mode - Teams
# =====================================================================

@router.post("/{arena_id}/teams", response_model=SuccessResponse[CreateTeamResponse])
async def create_team(
    arena_id: UUID,
    team_data: CreateTeamRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create a team for collaborative arena mode.

    **Requirements:**
    - Arena must be in `collaborative` mode
    - Teacher must teach the arena's class
    - Team name must be unique within the arena
    - All student_ids must be valid and enrolled in the class

    **Request:**
    ```json
    {
      "team_name": "Team Alpha",
      "student_ids": ["uuid1", "uuid2", "uuid3"],
      "leader_id": "uuid1"  // Optional: designate a team leader
    }
    ```

    **Response:**
    ```json
    {
      "data": {
        "success": true,
        "team": {
          "team_id": "uuid",
          "team_name": "Team Alpha",
          "members": [
            {"student_id": "uuid1", "student_name": "Alice", "role": "leader"},
            {"student_id": "uuid2", "student_name": "Bob", "role": "member"}
          ],
          "created_at": "2026-03-16T10:00:00Z"
        },
        "message": "Team created successfully"
      }
    }
    ```

    **Errors:**
    - 400: Validation error (duplicate name, students already in team, etc)
    - 404: Arena not found or access denied
    """
    log = get_logger(__name__)
    log.info("team_create_started")

    try:
        team = await ArenaService.create_team(
            db=db,
            arena_id=arena_id,
            teacher_id=current_user.id,
            team_name=team_data.team_name,
            student_ids=team_data.student_ids,
            leader_id=team_data.leader_id
        )
    except ValueError as e:
        log.warning(f"team_create_failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    if not team:
        log.warning("team_create_failed: access_denied")
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    from app.schemas.communication import TeamMemberInfo, TeamInfo
    members_info = [
        TeamMemberInfo(
            student_id=member.student_id,
            student_name=f"{member.student.first_name} {member.student.last_name}",
            role=member.role,
            avatar_url=member.student.profile_picture_url
        )
        for member in team.members
    ]

    log.info("team_created")

    return SuccessResponse(
        data=CreateTeamResponse(
            success=True,
            team=TeamInfo(
                team_id=team.id,
                team_name=team.team_name,
                members=members_info,
                created_at=team.created_at
            ),
            message="Team created successfully"
        ),
        message="Team created successfully"
    )


@router.post("/{arena_id}/teams/batch", response_model=SuccessResponse[BatchCreateTeamResponse])
async def create_teams_batch(
    arena_id: UUID,
    batch_data: BatchCreateTeamRequest,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create multiple teams for a collaborative arena in a single batch.
    
    This endpoint is more efficient and ensures all teams are created together.
    It performs validation to ensure unique team names and that students are 
    not assigned to multiple teams.
    
    **Teacher only** - requires arena ownership.
    """
    log = get_logger(__name__)
    log.info("teams_batch_create_started")

    # Convert Pydantic models to dicts for the service
    teams_list = [t.model_dump() for t in batch_data.teams]

    try:
        teams = await ArenaService.create_teams_batch(
            db=db,
            arena_id=arena_id,
            teacher_id=current_user.id,
            teams_data=teams_list
        )
    except ValueError as e:
        log.warning(f"teams_batch_create_failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

    from app.schemas.communication import TeamMemberInfo, TeamInfo
    
    created_teams_info = []
    for team in teams:
        members_info = [
            TeamMemberInfo(
                student_id=member.student_id,
                student_name=f"{member.student.first_name} {member.student.last_name}",
                role=member.role,
                avatar_url=member.student.profile_picture_url
            )
            for member in team.members
        ]
        created_teams_info.append(
            TeamInfo(
                team_id=team.id,
                team_name=team.team_name,
                members=members_info,
                created_at=team.created_at
            )
        )

    log.info("teams_batch_created")

    return SuccessResponse(
        data=BatchCreateTeamResponse(
            success=True,
            created_teams=created_teams_info,
            message=f"Successfully created {len(created_teams_info)} teams"
        ),
        message=f"Successfully created {len(created_teams_info)} teams"
    )


@router.get("/{arena_id}/teams", response_model=SuccessResponse[ListTeamsResponse])
async def list_teams(
    arena_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    List all teams for an arena (collaborative mode).

    **Response:**
    ```json
    {
      "data": {
        "arena_id": "uuid",
        "arena_mode": "collaborative",
        "teams": [
          {
            "team_id": "uuid",
            "team_name": "Team Alpha",
            "members": [
              {"student_id": "uuid1", "student_name": "Alice", "role": "leader"},
              {"student_id": "uuid2", "student_name": "Bob", "role": "member"}
            ],
            "created_at": "2026-03-16T10:00:00Z"
          }
        ],
        "total_teams": 3,
        "total_students": 12
      }
    }
    ```

    **Errors:**
    - 404: Arena not found or access denied
    """
    log = get_logger(__name__)

    teams = await ArenaService.list_teams(db, arena_id, current_user.id)

    if teams is None:
        log.warning("list_teams_failed")
        raise HTTPException(status_code=404, detail="Arena not found or access denied")

    # Get arena info
    arena = await ArenaService.get_arena(db, arena_id, current_user.id)

    # Build response
    from app.schemas.communication import TeamMemberInfo, TeamInfo

    teams_info = []
    total_students = 0

    for team in teams:
        members_info = [
            TeamMemberInfo(
                student_id=member.student_id,
                student_name=f"{member.student.first_name} {member.student.last_name}",
                role=member.role,
                avatar_url=member.student.profile_picture_url
            )
            for member in team.members
        ]

        teams_info.append(
            TeamInfo(
                team_id=team.id,
                team_name=team.team_name,
                members=members_info,
                created_at=team.created_at
            )
        )

        total_students += len(members_info)

    log.info("teams_listed")

    return SuccessResponse(
        data=ListTeamsResponse(
            arena_id=arena_id,
            arena_mode=arena.arena_mode or "unknown",
            teams=teams_info,
            total_teams=len(teams_info),
            total_students=total_students
        ),
        message=f"Found {len(teams_info)} teams with {total_students} total students"
    )

