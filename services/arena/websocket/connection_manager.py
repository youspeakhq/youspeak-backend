"""
WebSocket Connection Manager for Arena Live Sessions.
Manages WebSocket connections and broadcasts messages via Redis Pub/Sub.
"""

import json
import asyncio
import logging
from typing import Dict, List, Set, Optional, Any
from uuid import UUID
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis

from ..config import settings

logger = logging.getLogger(__name__)

MAX_CONNECTIONS_PER_ARENA = 100
MAX_CONNECTIONS_PER_USER = 5


class ArenaConnectionManager:
    def __init__(self, redis_url: Optional[str] = None):
        self.active_connections: Dict[UUID, List[WebSocket]] = {}
        self.user_connections: Dict[tuple, WebSocket] = {}
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[Any] = None
        self.pubsub_client: Optional[Any] = None
        self.pubsub_tasks: Dict[UUID, asyncio.Task] = {}
        self.use_redis = True

    async def initialize(self):
        if self.use_redis and self.redis_url:
            try:
                self.redis_client = await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
                self.pubsub_client = await aioredis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
                logger.info("Redis connection initialized for Arena Service")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory mode.")
                self.use_redis = False

    async def shutdown(self):
        if self.redis_client: await self.redis_client.close()
        if self.pubsub_client: await self.pubsub_client.close()
        for task in self.pubsub_tasks.values(): task.cancel()

    async def connect(self, arena_id: UUID, user_id: UUID, websocket: WebSocket):
        arena_conn_count = len(self.active_connections.get(arena_id, []))
        if arena_conn_count >= MAX_CONNECTIONS_PER_ARENA:
            await websocket.close(code=4008, reason="Arena connection limit reached")
            return

        user_conn_count = sum(1 for (aid, uid) in self.user_connections.keys() if uid == user_id)
        if user_conn_count >= MAX_CONNECTIONS_PER_USER:
            await websocket.close(code=4008, reason="User connection limit reached")
            return

        await websocket.accept()
        if arena_id not in self.active_connections: self.active_connections[arena_id] = []
        self.active_connections[arena_id].append(websocket)
        self.user_connections[(arena_id, user_id)] = websocket

        if self.use_redis and arena_id not in self.pubsub_tasks:
            self.pubsub_tasks[arena_id] = asyncio.create_task(self._redis_listener(arena_id))

    async def disconnect(self, arena_id: UUID, user_id: UUID, websocket: WebSocket):
        if arena_id in self.active_connections:
            if websocket in self.active_connections[arena_id]:
                self.active_connections[arena_id].remove(websocket)
            if not self.active_connections[arena_id]:
                del self.active_connections[arena_id]
                if arena_id in self.pubsub_tasks:
                    self.pubsub_tasks[arena_id].cancel()
                    del self.pubsub_tasks[arena_id]
        key = (arena_id, user_id)
        if key in self.user_connections: del self.user_connections[key]

    async def broadcast(self, arena_id: UUID, message: dict, exclude_user: Optional[UUID] = None):
        if "timestamp" not in message: message["timestamp"] = datetime.utcnow().isoformat()
        message_json = json.dumps(message)

        if self.use_redis and self.redis_client:
            channel = f"arena:{arena_id}:live"
            try:
                await asyncio.wait_for(self.redis_client.publish(channel, message_json), timeout=2.0)
            except Exception:
                await self._broadcast_local(arena_id, message, exclude_user)
        else:
            await self._broadcast_local(arena_id, message, exclude_user)

    async def _broadcast_local(self, arena_id: UUID, message: dict, exclude_user: Optional[UUID] = None):
        if arena_id not in self.active_connections: return
        connections = self.active_connections[arena_id].copy()
        if exclude_user:
            exclude_ws = self.user_connections.get((arena_id, exclude_user))
            if exclude_ws in connections: connections.remove(exclude_ws)
        if not connections: return
        message_json = json.dumps(message)
        send_tasks = [ws.send_text(message_json) for ws in connections]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        disconnected = [ws for ws, result in zip(connections, results) if isinstance(result, Exception)]
        for ws in disconnected:
            if ws in self.active_connections.get(arena_id, []): self.active_connections[arena_id].remove(ws)

    async def _redis_listener(self, arena_id: UUID):
        channel = f"arena:{arena_id}:live"
        try:
            pubsub = self.pubsub_client.pubsub()
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        msg_dict = json.loads(data)
                        await self._broadcast_local(arena_id, msg_dict)
                    except json.JSONDecodeError: pass
        except asyncio.CancelledError:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception as e:
            logger.error(f"Redis listener error for {channel}: {e}")

    async def send_personal_message(self, arena_id: UUID, user_id: UUID, message: dict):
        websocket = self.user_connections.get((arena_id, user_id))
        if websocket:
            if "timestamp" not in message: message["timestamp"] = datetime.utcnow().isoformat()
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                await self.disconnect(arena_id, user_id, websocket)

connection_manager = ArenaConnectionManager()
