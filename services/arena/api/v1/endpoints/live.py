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
from ....services.audio_stream_service import audio_stream_service
from ....services.core_api_client import core_api_client
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
    
    # Phase 2: Fetch arena metadata and participants from Core API
    arena_data = await core_api_client.get_arena_metadata(arena_id)
    
    if not arena_data:
        logger.warning(f"WebSocket connection rejected: arena {arena_id} not found or Core API error")
        await websocket.close(code=4004)  # Not Found
        return

    # Verify user is a participant
    participants = arena_data.get("participants", [])
    user_data = next((p for p in participants if UUID(p["user_id"]) == user_id), None)
    
    if not user_data:
        logger.warning(f"WebSocket connection rejected: user {user_id} is not a participant in arena {arena_id}")
        await websocket.close(code=4003)  # Forbidden
        return

    student_name = user_data.get("name", "Student")
    language_code = arena_data.get("language_code", "en")

    # Initialize connection
    await connection_manager.connect(arena_id, user_id, websocket)
    logger.info(f"User {user_id} ({student_name}) connected to arena {arena_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            
            # The frontend contract uses 'type' for event identification
            event_type = message.get("type")
            
            # Handle Audio Streaming for AI Analysis
            if event_type == "audio_chunk":
                payload = message.get("payload", "")
                if payload:
                    try:
                        audio_bytes = base64.b64decode(payload)
                        # Phase 3: Push to Redis Stream for background processing
                        await audio_stream_service.push_chunk(
                            arena_id=arena_id, 
                            user_id=user_id, 
                            audio_bytes=audio_bytes,
                            language_code=language_code,
                            metadata={"student_name": student_name}
                        )
                    except Exception as e:
                        logger.error(f"Error pushing audio chunk to stream: {e}")
            
            # Broadcast all other messages to participants in the same arena
            await connection_manager.broadcast(arena_id, message, exclude_user=user_id)
            
    except WebSocketDisconnect:
        await connection_manager.disconnect(arena_id, user_id, websocket)
        # Signal worker to close the audio session and release resources
        await audio_stream_service.push_chunk(
            arena_id=arena_id,
            user_id=user_id,
            event_type="session_end"
        )
        logger.info(f"User {user_id} disconnected from arena {arena_id}")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id} in arena {arena_id}: {e}")
        await connection_manager.disconnect(arena_id, user_id, websocket)
        await audio_stream_service.push_chunk(
            arena_id=arena_id,
            user_id=user_id,
            event_type="session_end"
        )
