import json
import logging
import base64
import zlib
from uuid import UUID
from typing import Optional, Any

import redis.asyncio as aioredis
from ..config import settings

logger = logging.getLogger(__name__)


class AudioStreamService:
    """Service for managing the audio chunk message bus with sharding."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[Any] = None
        self.base_stream_name = "arena:audio:chunks"
        self.total_shards = 8 # Configurable

    async def initialize(self):
        """Initializes the Redis client."""
        if not self.redis_client:
            try:
                self.redis_client = await aioredis.from_url(
                    self.redis_url, 
                    encoding="utf-8", 
                    decode_responses=True
                )
                logger.info("AudioStreamService initialized")
            except Exception as e:
                logger.error(f"Failed to initialize AudioStreamService: {e}")

    def _get_shard_id(self, user_id: UUID) -> int:
        """Calculates a deterministic shard ID for a user."""
        return zlib.crc32(str(user_id).encode()) % self.total_shards

    async def push_chunk(
        self, 
        arena_id: UUID, 
        user_id: UUID, 
        audio_bytes: Optional[bytes] = None, 
        language_code: str = "en",
        event_type: str = "audio_chunk",
        metadata: Optional[dict] = None
    ):
        """
        Pushes an audio event to a sharded Redis stream.
        Ensures all events for a user land on the same worker instance.
        """
        if not self.redis_client:
            await self.initialize()
            
        if not self.redis_client:
            logger.error("Redis client not available")
            return

        shard_id = self._get_shard_id(user_id)
        stream_name = f"{self.base_stream_name}:{shard_id}"

        try:
            message = {
                "event_type": event_type,
                "arena_id": str(arena_id),
                "user_id": str(user_id),
                "language_code": language_code,
                "metadata": json.dumps(metadata or {})
            }
            
            if audio_bytes:
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                message["audio_payload"] = audio_b64
            
            # XADD to the sharded stream
            await self.redis_client.xadd(
                stream_name, 
                message, 
                maxlen=5000, 
                approximate=True
            )
        except Exception as e:
            logger.error(f"Error pushing {event_type} to stream {stream_name}: {e}")


audio_stream_service = AudioStreamService()
