"""
Audio Analysis Worker for Arena.
Consumes audio chunks from Redis Streams and performs AI analysis.
Broadcasts results back to the arena via Redis Pub/Sub.
"""

import asyncio
import logging
import base64
import json
import os
from uuid import UUID
import redis.asyncio as aioredis

from ..config import settings
from ..services.audio_analysis_service import audio_analysis_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audio_worker")


async def run_audio_worker():
    """
    Main worker loop.
    Reads events from multiple sharded Redis Streams and processes them.
    """
    redis_url = settings.REDIS_URL
    base_stream_name = "arena:audio:chunks"
    group_name = "audio_processors"
    consumer_name = f"worker-{os.getpid()}"
    
    # Configuration for sharding (can be injected via ENV)
    num_shards = 8
    # By default, a worker listens to all shards. Scale-out involves restricting this list.
    assigned_shards = list(range(num_shards))
    stream_names = {f"{base_stream_name}:{i}": ">" for i in assigned_shards}

    logger.info(f"Connecting to Redis at {redis_url}")
    redis_client = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    # Create consumer groups for all assigned shards
    for stream_name in stream_names.keys():
        try:
            await redis_client.xgroup_create(stream_name, group_name, id="0", mkstream=True)
            logger.info(f"Created consumer group {group_name} for stream {stream_name}")
        except Exception as e:
            if "BUSYGROUP" in str(e):
                continue
            logger.error(f"Error creating group for {stream_name}: {e}")

    # Set up broadcast callback
    async def _broadcast_to_redis(arena_id, data: dict):
        channel = f"arena:{arena_id}:live"
        if "timestamp" not in data:
            from datetime import datetime
            data["timestamp"] = datetime.utcnow().isoformat()
        await redis_client.publish(channel, json.dumps(data))

    audio_analysis_service.set_broadcast_callback(_broadcast_to_redis)

    logger.info(f"Audio Worker {consumer_name} listening to {len(stream_names)} shards...")

    while True:
        try:
            # Read from all assigned streams
            messages = await redis_client.xreadgroup(
                group_name, 
                consumer_name, 
                stream_names, 
                count=1, 
                block=5000
            )
            
            if not messages:
                continue

            for stream, msgs in messages:
                for msg_id, payload in msgs:
                    try:
                        event_type = payload.get("event_type", "audio_chunk")
                        arena_id = UUID(payload["arena_id"])
                        user_id = UUID(payload["user_id"])
                        
                        if event_type == "session_end":
                            logger.info(f"Closing session for user {user_id} in arena {arena_id}")
                            await audio_analysis_service.close_session(arena_id, user_id)
                        
                        elif event_type == "audio_chunk":
                            audio_b64 = payload.get("audio_payload")
                            if not audio_b64:
                                await redis_client.xack(stream, group_name, msg_id)
                                continue
                                
                            language_code = payload.get("language_code", "en")
                            metadata = json.loads(payload.get("metadata", "{}"))
                            student_name = metadata.get("student_name", "Student")
                            
                            audio_bytes = base64.b64decode(audio_b64)
                            
                            # Process audio
                            await audio_analysis_service.start_session(
                                arena_id=arena_id, 
                                user_id=user_id, 
                                language_code=language_code,
                                student_name=student_name
                            )
                            await audio_analysis_service.process_audio_chunk(arena_id, user_id, audio_bytes)
                        
                        # Acknowledge
                        await redis_client.xack(stream, group_name, msg_id)
                        
                    except Exception as pe:
                        logger.error(f"Error processing message {msg_id} from {stream}: {pe}")
                        await redis_client.xack(stream, group_name, msg_id)
                        
        except asyncio.CancelledError:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Worker main loop error: {e}")
            await asyncio.sleep(2)

    await redis_client.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_audio_worker())
    except KeyboardInterrupt:
        pass
