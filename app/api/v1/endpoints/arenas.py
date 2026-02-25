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
