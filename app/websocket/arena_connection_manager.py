"""
WebSocket Connection Manager for Arena Live Sessions.

Manages WebSocket connections and broadcasts messages via Redis Pub/Sub
to enable horizontal scaling across multiple backend servers.
"""

import json
import asyncio
from typing import Dict, List, Set, Optional
from uuid import UUID
from datetime import datetime
import logging

from fastapi import WebSocket, WebSocketDisconnect

# Redis imports with graceful degradation
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None

logger = logging.getLogger(__name__)

# Connection limits
MAX_CONNECTIONS_PER_ARENA = 100
MAX_CONNECTIONS_PER_USER = 5


class ArenaConnectionManager:
    """
    Manages WebSocket connections for arena live sessions.

    Uses Redis Pub/Sub to broadcast messages across multiple server instances,
    enabling horizontal scaling.

    Architecture:
    - Each backend server maintains local WebSocket connections
    - Redis channels broadcast messages to all servers
    - Each server forwards messages to its local connections
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize connection manager.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379)
                      If None, falls back to in-memory mode (single server only)
        """
        # Local WebSocket connections: {arena_id: [websocket, ...]}
        self.active_connections: Dict[UUID, List[WebSocket]] = {}

        # Track which user is on which connection: {(arena_id, user_id): websocket}
        self.user_connections: Dict[tuple, WebSocket] = {}

        # Redis clients
        self.redis_url = redis_url
        self.redis_client: Optional[aioredis.Redis] = None
        self.pubsub_client: Optional[aioredis.Redis] = None

        # Pubsub listeners: {arena_id: asyncio.Task}
        self.pubsub_tasks: Dict[UUID, asyncio.Task] = {}

        # Mode
        self.use_redis = HAS_REDIS and redis_url is not None

    async def initialize(self):
        """Initialize Redis connection if available."""
        if self.use_redis and self.redis_url:
            try:
                self.redis_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                self.pubsub_client = await aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True
                )
                logger.info("Redis connection initialized for WebSocket broadcasting")
            except Exception as e:
                logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory mode.")
                self.use_redis = False

    async def shutdown(self):
        """Shutdown Redis connections."""
        if self.redis_client:
            await self.redis_client.close()
        if self.pubsub_client:
            await self.pubsub_client.close()

        # Cancel all pubsub listener tasks
        for task in self.pubsub_tasks.values():
            task.cancel()

    async def connect(
        self,
        arena_id: UUID,
        user_id: UUID,
        websocket: WebSocket
    ):
        """
        Accept WebSocket connection and subscribe to arena channel.

        Enforces connection limits:
        - Max 100 connections per arena
        - Max 5 connections per user (across all arenas)

        Args:
            arena_id: Arena session ID
            user_id: Connected user ID
            websocket: WebSocket connection

        Raises:
            Closes WebSocket with code 4008 if connection limit exceeded
        """
        # Check arena connection limit
        arena_conn_count = len(self.active_connections.get(arena_id, []))
        if arena_conn_count >= MAX_CONNECTIONS_PER_ARENA:
            logger.warning(
                f"Arena connection limit reached: arena={arena_id}, count={arena_conn_count}"
            )
            await websocket.close(code=4008, reason="Arena connection limit reached")
            return

        # Check user connection limit (across all arenas)
        user_conn_count = sum(
            1 for (aid, uid) in self.user_connections.keys()
            if uid == user_id
        )
        if user_conn_count >= MAX_CONNECTIONS_PER_USER:
            logger.warning(
                f"User connection limit reached: user={user_id}, count={user_conn_count}"
            )
            await websocket.close(code=4008, reason="User connection limit reached")
            return

        await websocket.accept()

        # Add to local connections
        if arena_id not in self.active_connections:
            self.active_connections[arena_id] = []
        self.active_connections[arena_id].append(websocket)

        # Track user connection
        self.user_connections[(arena_id, user_id)] = websocket

        # Subscribe to Redis channel for this arena (if first connection)
        if self.use_redis and arena_id not in self.pubsub_tasks:
            task = asyncio.create_task(self._redis_listener(arena_id))
            self.pubsub_tasks[arena_id] = task

        logger.info(f"WebSocket connected: arena={arena_id}, user={user_id}, total_arena_conns={arena_conn_count + 1}")

    async def disconnect(
        self,
        arena_id: UUID,
        user_id: UUID,
        websocket: WebSocket
    ):
        """
        Remove WebSocket connection.

        Args:
            arena_id: Arena session ID
            user_id: Disconnected user ID
            websocket: WebSocket connection
        """
        # Remove from local connections
        if arena_id in self.active_connections:
            if websocket in self.active_connections[arena_id]:
                self.active_connections[arena_id].remove(websocket)

            # Clean up empty arena
            if not self.active_connections[arena_id]:
                del self.active_connections[arena_id]

                # Cancel Redis listener if no more local connections
                if arena_id in self.pubsub_tasks:
                    self.pubsub_tasks[arena_id].cancel()
                    del self.pubsub_tasks[arena_id]

        # Remove user connection tracking
        key = (arena_id, user_id)
        if key in self.user_connections:
            del self.user_connections[key]

        logger.info(f"WebSocket disconnected: arena={arena_id}, user={user_id}")

    async def broadcast(
        self,
        arena_id: UUID,
        message: dict,
        exclude_user: Optional[UUID] = None
    ):
        """
        Broadcast message to all connected clients in arena.

        If Redis is enabled, publishes to Redis channel (reaching all servers).
        Otherwise, broadcasts to local connections only (single server mode).

        Circuit breaker: Falls back to local broadcast if Redis fails or times out.

        Args:
            arena_id: Arena to broadcast to
            message: Message dict (will be JSON-serialized)
            exclude_user: Optional user_id to exclude from broadcast
        """
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()

        message_json = json.dumps(message)

        if self.use_redis and self.redis_client:
            # Publish to Redis channel (all servers will receive)
            channel = f"arena:{arena_id}:live"
            try:
                # Timeout after 2 seconds (circuit breaker pattern)
                await asyncio.wait_for(
                    self.redis_client.publish(channel, message_json),
                    timeout=2.0
                )
                logger.debug(f"Broadcasted to Redis channel {channel}")
            except asyncio.TimeoutError:
                logger.error(f"Redis broadcast timeout for {channel}, falling back to local")
                # Fallback to local broadcast
                await self._broadcast_local(arena_id, message, exclude_user)
            except Exception as e:
                logger.error(f"Redis broadcast error: {e}, falling back to local")
                # Fallback to local broadcast
                await self._broadcast_local(arena_id, message, exclude_user)
        else:
            # In-memory mode: broadcast to local connections only
            await self._broadcast_local(arena_id, message, exclude_user)

    async def _broadcast_local(
        self,
        arena_id: UUID,
        message: dict,
        exclude_user: Optional[UUID] = None
    ):
        """
        Broadcast message to local WebSocket connections only.

        Uses parallel sends for better performance with many connections.

        Args:
            arena_id: Arena to broadcast to
            message: Message dict
            exclude_user: Optional user_id to exclude
        """
        if arena_id not in self.active_connections:
            return

        # Get connections to broadcast to
        connections = self.active_connections[arena_id].copy()

        # Filter out excluded user if specified
        if exclude_user:
            exclude_ws = self.user_connections.get((arena_id, exclude_user))
            if exclude_ws in connections:
                connections.remove(exclude_ws)

        if not connections:
            return

        # Send to all remaining connections in parallel
        message_json = json.dumps(message)

        # Create send tasks for all connections
        send_tasks = [ws.send_text(message_json) for ws in connections]

        # Execute all sends in parallel, capture exceptions
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        # Handle failed sends (disconnect)
        disconnected = [
            ws for ws, result in zip(connections, results)
            if isinstance(result, Exception)
        ]

        # Clean up disconnected websockets
        if disconnected:
            logger.debug(f"Cleaning up {len(disconnected)} disconnected websockets in arena {arena_id}")
            for ws in disconnected:
                if ws in self.active_connections.get(arena_id, []):
                    self.active_connections[arena_id].remove(ws)

    async def _redis_listener(self, arena_id: UUID):
        """
        Listen to Redis Pub/Sub channel and forward messages to local connections.

        This task runs continuously while there are local connections for this arena.

        Args:
            arena_id: Arena to listen for
        """
        channel = f"arena:{arena_id}:live"

        try:
            pubsub = self.pubsub_client.pubsub()
            await pubsub.subscribe(channel)

            logger.info(f"Redis listener started for {channel}")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    try:
                        msg_dict = json.loads(data)
                        # Forward to local connections
                        await self._broadcast_local(arena_id, msg_dict, exclude_user=None)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from Redis: {data}")

        except asyncio.CancelledError:
            logger.info(f"Redis listener cancelled for {channel}")
            await pubsub.unsubscribe(channel)
            await pubsub.close()
        except Exception as e:
            logger.error(f"Redis listener error for {channel}: {e}")

    async def send_personal_message(
        self,
        arena_id: UUID,
        user_id: UUID,
        message: dict
    ):
        """
        Send message to a specific user only.

        Args:
            arena_id: Arena session
            user_id: Target user
            message: Message dict
        """
        websocket = self.user_connections.get((arena_id, user_id))
        if websocket:
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()

            try:
                await websocket.send_text(json.dumps(message))
            except WebSocketDisconnect:
                await self.disconnect(arena_id, user_id, websocket)
            except Exception as e:
                logger.error(f"Error sending personal message: {e}")

    def get_connection_count(self, arena_id: UUID) -> int:
        """Get number of local connections for an arena."""
        return len(self.active_connections.get(arena_id, []))

    def get_connected_users(self, arena_id: UUID) -> Set[UUID]:
        """Get set of user IDs connected to an arena (local connections only)."""
        return {
            user_id for (aid, user_id) in self.user_connections.keys()
            if aid == arena_id
        }


# Global connection manager instance
connection_manager = ArenaConnectionManager()
