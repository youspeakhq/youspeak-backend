from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.models.enums import ActivityActionType
from app.services.school_service import SchoolService
from app.services.activity_service import ActivityService
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.schemas.admin import (
    AdminStats,
    LeaderboardResponse,
    ActivityLogCreate,
    ActivityLogOut,
)

router = APIRouter()


@router.get("/stats", response_model=SuccessResponse[AdminStats])
async def get_admin_stats(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Aggregated dashboard statistics for the school.
    Returns active classes count, total students, and total teachers.
    """
    stats = await SchoolService.get_stats(db, current_user.school_id)
    return SuccessResponse(data=AdminStats(**stats), message="Stats retrieved successfully")


@router.get("/activity", response_model=PaginatedResponse[ActivityLogOut])
async def get_activity_log(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    action_type: Optional[ActivityActionType] = Query(None, description="Filter by action type"),
) -> Any:
    """
    Global school activity log (Figma: Activity Log). Paginated, optional filter by action type.
    """
    items, total = await ActivityService.list_activity(
        db, current_user.school_id, page=page, page_size=page_size, action_type=action_type
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[ActivityLogOut(**x) for x in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
        message="Activity log retrieved successfully",
    )


@router.post("/activity", response_model=SuccessResponse[ActivityLogOut])
async def create_activity_log_entry(
    payload: ActivityLogCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Append an entry to the school activity log. The current admin is recorded as performer.
    """
    log = await ActivityService.create(
        db, current_user.school_id, payload, performed_by_user_id=current_user.id
    )
    performer_name = current_user.full_name
    out = ActivityLogOut(
        id=log.id,
        action_type=log.action_type,
        description=log.description,
        performed_by_user_id=log.performed_by_user_id,
        performer_name=performer_name,
        target_entity_type=log.target_entity_type,
        target_entity_id=log.target_entity_id,
        created_at=log.created_at,
    )
    return SuccessResponse(data=out, message="Activity logged successfully")


@router.get("/leaderboard", response_model=SuccessResponse[LeaderboardResponse])
async def get_leaderboard(
    timeframe: str = "week",
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Top performing students and classes by arena points (Figma: Students leaderboard).
    Timeframe: week | month | all.
    """
    data = await SchoolService.get_leaderboard(db, current_user.school_id, timeframe=timeframe)
    return SuccessResponse(data=data, message="Leaderboard retrieved successfully")
