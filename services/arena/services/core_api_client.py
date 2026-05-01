"""
Core API Client for inter-service communication.
Used by Arena service to fetch metadata and verify users from the Core API.
"""

import httpx
import logging
from uuid import UUID
from typing import Dict, Any, Optional
from ..config import settings

logger = logging.getLogger(__name__)


class CoreAPIClient:
    """Client for communicating with the YouSpeak Core API."""
    
    def __init__(self):
        self.base_url = settings.CORE_SERVICE_URL.rstrip("/")
        self.headers = {
            "X-Internal-Secret": settings.INTERNAL_API_SECRET,
            "Content-Type": "application/json"
        }

    async def get_arena_metadata(self, arena_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Fetches arena metadata and participant list from the Core API.
        """
        url = f"{self.base_url}/api/v1/internal/arenas/{arena_id}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self.headers)
                if response.status_code == 200:
                    return response.json()
                
                logger.error(f"Core API returned error for arena {arena_id}: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch arena metadata from Core API: {e}")
            return None

    async def verify_token(self, token: str) -> Optional[UUID]:
        """
        Verifies a user token via the Core API.
        """
        url = f"{self.base_url}/api/v1/internal/verify-token"
        params = {"token": token}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return UUID(data["user_id"])
                return None
        except Exception as e:
            logger.error(f"Failed to verify token with Core API: {e}")
            return None


core_api_client = CoreAPIClient()
