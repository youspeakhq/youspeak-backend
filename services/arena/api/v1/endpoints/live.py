"""
Live Arena WebSocket Endpoint.
Handles real-time communication, audio streaming, and AI analysis broadcasting.
"""

import base64
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....websocket.connection_manager import connection_manager
from ....services.audio_analysis_service import audio_analysis_service
from ....database import get_db
from ....security import get_user_id_from_token
from ....models import Arena

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/{arena_id}/ws")
async def arena_websocket(
    websocket: WebSocket,
    arena_id: UUID,
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for live arena sessions.
    
    Query Params:
        token: JWT access token for authentication
    """
    user_id_str = get_user_id_from_token(token)
    if not user_id_str:
        logger.warning(f"WebSocket connection rejected: invalid token for arena {arena_id}")
        await websocket.close(code=4003)  # Forbidden
        return
    
    user_id = UUID(user_id_str)
    
    # Phase 1: Verify arena existence via shared database
    # In Phase 2, this will move to an internal API call to the Core service
    result = await db.execute(select(Arena).where(Arena.id == arena_id))
    arena = result.scalar_one_or_none()
    
    if not arena:
        logger.warning(f"WebSocket connection rejected: arena {arena_id} not found")
        await websocket.close(code=4004)  # Not Found
        return

    # Initialize connection
    await connection_manager.connect(arena_id, user_id, websocket)
    logger.info(f"User {user_id} connected to arena {arena_id}")
    
    try:
        # Start audio analysis session if it's a student (optional, based on role)
        # For Phase 1, we start it for everyone who sends audio
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            
            event_type = message.get("type")
            
            # Handle Audio Streaming for AI Analysis
            if event_type == "audio_chunk":
                payload = message.get("payload", "")
                if payload:
                    try:
                        audio_bytes = base64.b64decode(payload)
                        # Ensure session is started (idempotent)
                        # We use "Student" as a placeholder name for now
                        await audio_analysis_service.start_session(
                            arena_id=arena_id, 
                            user_id=user_id, 
                            language_code="en" # TODO: Get from arena metadata
                        )
                        await audio_analysis_service.process_audio_chunk(arena_id, user_id, audio_bytes)
                    except Exception as e:
                        logger.error(f"Error processing audio chunk: {e}")
            
            # Broadcast all other messages to participants in the same arena
            await connection_manager.broadcast(arena_id, message, exclude_user=user_id)
            
    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from arena {arena_id}")
        await connection_manager.disconnect(arena_id, user_id, websocket)
        await audio_analysis_service.close_session(arena_id, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id} in arena {arena_id}: {e}")
        await connection_manager.disconnect(arena_id, user_id, websocket)
        await audio_analysis_service.close_session(arena_id, user_id)
