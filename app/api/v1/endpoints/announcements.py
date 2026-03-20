from typing import Any, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.communication import AnnouncementCreate, AnnouncementResponse, AnnouncementListResponse
from app.schemas.responses import SuccessResponse
from app.services.communication_service import CommunicationService

router = APIRouter()


@router.get("", response_model=AnnouncementListResponse)
async def list_announcements(
    class_id: Optional[UUID] = Query(None, description="Filter by class ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    List announcements for the current school.
    Teachers can filter by class_id.
    """
    items, total = await CommunicationService.list_announcements(
        db,
        school_id=current_user.school_id,
        class_id=class_id,
        page=page,
        page_size=page_size,
    )
    
    return AnnouncementListResponse(announcements=items, total=total)


@router.post("", response_model=SuccessResponse[AnnouncementResponse])
async def create_announcement(
    announcement_in: AnnouncementCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Create a new announcement (Teacher only).
    """
    announcement = await CommunicationService.create_announcement(
        db,
        author_id=current_user.id,
        school_id=current_user.school_id,
        payload=announcement_in,
    )
    
    return SuccessResponse(
        data=AnnouncementResponse.model_validate(announcement),
        message="Announcement created successfully"
    )


@router.delete("/{announcement_id}", response_model=SuccessResponse)
async def delete_announcement(
    announcement_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Delete an announcement (Teacher only).
    """
    # Verify authorship or admin status
    announcement = await CommunicationService.get_announcement_by_id(db, announcement_id)
    if not announcement:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    if announcement.author_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this announcement")
    
    success = await CommunicationService.delete_announcement(db, announcement_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete announcement")
    
    return SuccessResponse(data=None, message="Announcement deleted successfully")
