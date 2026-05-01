"""
Arena Audio Management Endpoints.
Handles Cloudflare RealtimeKit token generation.
"""

from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....services.realtimekit_service import realtimekit_service
from ....database import get_db
from ....security import get_user_id_from_token
from ....models import Arena

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/{arena_id}/token")
async def generate_audio_token(
    arena_id: UUID,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Cloudflare RealtimeKit audio token.
    """
    user_id_str = get_user_id_from_token(token)
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = UUID(user_id_str)
    
    # Phase 1: Shared DB lookup
    result = await db.execute(select(Arena).where(Arena.id == arena_id))
    arena = result.scalar_one_or_none()
    
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
        
    # TODO: Verify participant status
    
    # Get or create meeting
    meeting_data = await realtimekit_service.create_meeting(
        arena_id=arena_id,
        title=f"Arena: {arena.title}"
    )
    
    if not meeting_data:
        raise HTTPException(status_code=500, detail="Failed to create audio meeting")
        
    meeting_id = meeting_data["id"]
    
    # Add participant
    # Note: We don't have the user name here, we'd need to fetch it from DB or token
    participant_data = await realtimekit_service.add_participant(
        meeting_id=meeting_id,
        user_id=user_id,
        user_name="User" # Placeholder
    )
    
    if not participant_data:
        raise HTTPException(status_code=500, detail="Failed to join audio meeting")
        
    return {
        "token": participant_data["token"],
        "meeting_id": meeting_id,
        "participant_id": participant_data["id"]
    }
