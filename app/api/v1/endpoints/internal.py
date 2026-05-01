"""
Internal API Endpoints for Inter-Service Communication.
Used by Arena and Curriculum services to fetch metadata and verify users.
"""

from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from ....database import get_db
from ....config import settings
from ....models import Arena, ArenaParticipant

router = APIRouter()
logger = logging.getLogger(__name__)


async def verify_internal_secret(x_internal_secret: str = Header(None)):
    """Verifies that the request comes from an internal service."""
    if not x_internal_secret or x_internal_secret != settings.INTERNAL_API_SECRET:
        logger.warning(f"Unauthorized internal API access attempt")
        raise HTTPException(status_code=401, detail="Invalid internal secret")


@router.get("/arenas/{arena_id}", dependencies=[Depends(verify_internal_secret)])
async def get_arena_internal(
    arena_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """
    Returns arena metadata and participant list.
    Called by the Arena microservice to verify session context.
    """
    # Fetch arena
    result = await db.execute(select(Arena).where(Arena.id == arena_id))
    arena = result.scalar_one_or_none()
    
    if not arena:
        raise HTTPException(status_code=404, detail="Arena not found")
        
    # Get participants
    p_result = await db.execute(select(ArenaParticipant).where(ArenaParticipant.arena_id == arena_id))
    participants = p_result.scalars().all()
    
    return {
        "id": arena.id,
        "title": arena.title,
        "status": arena.status,
        "language_code": "en", # Default for now
        "participants": [
            {
                "user_id": p.user_id, 
                "role": p.role,
                # In Phase 3, we could add more details here to avoid the Arena service 
                # needing to query the user table at all.
            } for p in participants
        ]
    }


@router.get("/verify-token", dependencies=[Depends(verify_internal_secret)])
async def verify_user_token(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verifies a user token and returns user details.
    Allows microservices to verify auth without sharing the JWT secret if desired.
    """
    from ....security import get_user_id_from_token
    user_id_str = get_user_id_from_token(token)
    
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")
        
    return {"user_id": user_id_str}
