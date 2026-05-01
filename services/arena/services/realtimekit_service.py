"""
Cloudflare RealtimeKit Service for Arena Service.
Handles meeting creation and participant management for real-time audio conferencing.
"""

import httpx
import logging
from typing import Optional, Dict, Any
from uuid import UUID

from ..config import settings

logger = logging.getLogger(__name__)


class CloudflareRealtimeKitService:
    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.app_id = settings.CLOUDFLARE_REALTIMEKIT_APP_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/realtime/kit/{self.app_id}"

        if not all([self.account_id, self.app_id, self.api_token]):
            logger.warning("Cloudflare RealtimeKit credentials not configured.")

    async def create_meeting(
        self, arena_id: UUID, title: str, record_on_start: bool = True,
        enable_transcription: bool = True, transcription_language: str = "en-US"
    ) -> Optional[Dict[str, Any]]:
        if not self._credentials_configured(): return None
        payload = {"title": title, "record_on_start": record_on_start, "persist_chat": False}
        if enable_transcription:
            payload["ai_config"] = {"transcription": {"language": transcription_language, "keywords": [], "profanity_filter": False}}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/meetings", json=payload,
                    headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
                    timeout=10.0
                )
                if response.status_code in (200, 201):
                    return (response.json().get("data") or response.json().get("result") or {})
                return None
        except Exception as e:
            logger.error(f"Error creating meeting: {e}")
            return None

    async def add_participant(
        self, meeting_id: str, user_id: UUID, user_name: str, preset_name: str = "group_call_participant"
    ) -> Optional[Dict[str, Any]]:
        if not self._credentials_configured(): return None
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/meetings/{meeting_id}/participants",
                    json={"custom_participant_id": str(user_id), "preset_name": preset_name, "name": user_name},
                    headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
                    timeout=10.0
                )
                if response.status_code in (200, 201):
                    return (response.json().get("data") or response.json().get("result") or {})
                return None
        except Exception as e:
            logger.error(f"Error adding participant: {e}")
            return None

    async def verify_meeting(self, meeting_id: str) -> bool:
        if not self._credentials_configured(): return False
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}",
                    headers={"Authorization": f"Bearer {self.api_token}"}, timeout=5.0
                )
                return response.status_code == 200
        except Exception: return False

    def _credentials_configured(self) -> bool:
        return all([self.account_id, self.app_id, self.api_token])

realtimekit_service = CloudflareRealtimeKitService()
