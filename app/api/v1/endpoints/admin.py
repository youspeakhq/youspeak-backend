from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.services.school_service import SchoolService
from app.schemas.responses import SuccessResponse

router = APIRouter()

@router.get("/stats", response_model=SuccessResponse[Dict[str, int]])
async def get_admin_stats(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Aggregated counts (Active Classes, Students).
    """
    stats = await SchoolService.get_stats(db, current_user.school_id)
    return SuccessResponse(data=stats)

@router.get("/activity", response_model=SuccessResponse)
async def get_activity_log(
    limit: int = 10,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Global school activity log.
    """
    # Mock data for now until ActivityLog model is connected
    activities = [
        {"id": 1, "action": "New Student Registered", "timestamp": "2024-01-28T10:00:00Z"},
        {"id": 2, "action": "Class Created: French 101", "timestamp": "2024-01-28T09:30:00Z"}
    ]
    return SuccessResponse(data=activities)

@router.get("/leaderboard", response_model=SuccessResponse)
async def get_leaderboard(
    timeframe: str = "week",
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Top performing classes/students.
    """
    # Mock data for now
    leaderboard = {
        "top_classes": [
            {"name": "Spanish 101", "score": 950},
            {"name": "French 202", "score": 880}
        ],
        "top_students": [
            {"name": "John Doe", "score": 120},
            {"name": "Jane Smith", "score": 115}
        ]
    }
    return SuccessResponse(data=leaderboard)
