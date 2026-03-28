"""
Cloudflare RealtimeKit Service

Handles meeting creation and participant management for real-time audio conferencing.
Documentation: https://developers.cloudflare.com/realtime/realtimekit/
"""

import httpx
from typing import Optional, Dict, Any
from uuid import UUID

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CloudflareRealtimeKitService:
    """
    Service for managing Cloudflare RealtimeKit audio conferencing.

    RealtimeKit provides real-time WebRTC audio infrastructure on Cloudflare's
    global edge network (335+ locations).

    Architecture:
    1. Create Meeting (reusable room) via REST API
    2. Add Participant via REST API → Cloudflare returns authToken
    3. Frontend uses authToken to join with RealtimeKit SDK

    Features:
    - Host/Audience role-based access via presets
    - <50ms latency globally
    - Cloud recording to R2
    - Integration with Workers AI for transcription
    """

    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.app_id = settings.CLOUDFLARE_REALTIMEKIT_APP_ID
        self.api_token = settings.CLOUDFLARE_API_TOKEN
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/realtime/kit/{self.app_id}"

        if not all([self.account_id, self.app_id, self.api_token]):
            logger.warning("Cloudflare RealtimeKit credentials not configured. Audio will not work.")

    async def create_meeting(
        self,
        arena_id: UUID,
        title: str,
        record_on_start: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Create a RealtimeKit meeting (reusable room).

        Args:
            arena_id: Arena UUID (used in meeting title/metadata)
            title: Meeting title
            record_on_start: Auto-start recording when first participant joins

        Returns:
            {
                "id": "meeting_uuid",
                "title": "Arena: Speaking Challenge",
                "created_at": "2026-03-24T12:00:00Z"
            }
        """
        if not self._credentials_configured():
            logger.error("Cannot create meeting: RealtimeKit credentials not configured")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/meetings",
                    json={
                        "title": title,
                        "record_on_start": record_on_start,
                        "persist_chat": False
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    meeting_data = result.get("result", {})
                    logger.info(f"Meeting created for arena {arena_id}", extra={
                        "meeting_id": meeting_data.get("id"),
                        "arena_id": str(arena_id)
                    })
                    return meeting_data
                else:
                    logger.error(
                        f"Failed to create meeting: HTTP {response.status_code}",
                        extra={"response_body": response.text, "arena_id": str(arena_id)}
                    )
                    return None

        except Exception as e:
            logger.error(f"Error creating meeting: {e}", exc_info=True)
            return None

    async def add_participant(
        self,
        meeting_id: str,
        user_id: UUID,
        user_name: str,
        preset_name: str = "group_call_participant"  # "group_call_host" or "group_call_participant"
    ) -> Optional[Dict[str, Any]]:
        """
        Add participant to meeting and get authToken from Cloudflare.

        Args:
            meeting_id: RealtimeKit meeting ID (from create_meeting)
            user_id: User UUID (used as custom_participant_id)
            user_name: User display name
            preset_name: Preset defining permissions ("teacher-host" or "student-audience")

        Returns:
            {
                "id": "participant_uuid",
                "token": "auth_token_for_frontend",  # This is what frontend uses to join
                "custom_participant_id": "user_uuid",
                "preset_name": "student-audience",
                "name": "John Doe",
                "created_at": "2026-03-24T12:00:00Z"
            }
        """
        if not self._credentials_configured():
            logger.error("Cannot add participant: RealtimeKit credentials not configured")
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/meetings/{meeting_id}/participants",
                    json={
                        "custom_participant_id": str(user_id),
                        "preset_name": preset_name,
                        "name": user_name
                    },
                    headers={
                        "Authorization": f"Bearer {self.api_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    participant_data = result.get("result", {})
                    logger.info(f"Participant added to meeting", extra={
                        "meeting_id": meeting_id,
                        "user_id": str(user_id),
                        "preset": preset_name
                    })
                    return participant_data
                else:
                    logger.error(
                        f"Failed to add participant: HTTP {response.status_code}",
                        extra={
                            "response_body": response.text,
                            "meeting_id": meeting_id,
                            "preset_name": preset_name,
                        }
                    )
                    return None

        except Exception as e:
            logger.error(f"Error adding participant: {e}", exc_info=True)
            return None

    async def get_or_create_meeting(
        self,
        arena_id: UUID,
        arena_title: str,
        existing_meeting_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get existing meeting or create new one if needed.
        Verifies the existing meeting is still valid on Cloudflare before trusting it.
        """
        if existing_meeting_id:
            # Verify it still exists on Cloudflare
            is_valid = await self.verify_meeting(existing_meeting_id)
            if is_valid:
                return {"id": existing_meeting_id}
            else:
                logger.warning(
                    f"Cached meeting_id {existing_meeting_id} no longer exists on Cloudflare "
                    f"for arena {arena_id}. Creating a new meeting."
                )

        # Create new meeting
        return await self.create_meeting(
            arena_id=arena_id,
            title=f"Arena: {arena_title}",
            record_on_start=True
        )

    async def verify_meeting(self, meeting_id: str) -> bool:
        """
        Verify a meeting still exists on Cloudflare.
        Returns True if valid, False if not found or error.
        """
        if not self._credentials_configured():
            return False

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}",
                    headers={"Authorization": f"Bearer {self.api_token}"},
                    timeout=5.0
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"Error verifying meeting {meeting_id}: {e}")
            return False

    async def start_recording(
        self,
        arena_id: UUID,
        meeting_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Start cloud recording for meeting.

        Note: If meeting was created with record_on_start=True,
        recording starts automatically when first participant joins.

        Args:
            arena_id: Arena UUID
            meeting_id: RealtimeKit meeting ID

        Returns:
            Recording metadata or None if error
        """
        # RealtimeKit auto-records if record_on_start=True
        # This is a placeholder for explicit recording control
        logger.info(f"Recording auto-started for arena {arena_id} (record_on_start=True)")
        return {
            "status": "recording",
            "meeting_id": meeting_id,
            "note": "Auto-recording enabled on meeting creation"
        }

    async def stop_recording(
        self,
        meeting_id: str,
        recording_id: str
    ) -> bool:
        """
        Stop cloud recording.

        Recording stops automatically when last participant leaves.
        This is a placeholder for explicit control.

        Args:
            meeting_id: RealtimeKit meeting ID
            recording_id: Recording session ID

        Returns:
            True if stopped successfully
        """
        logger.info(f"Recording will stop when last participant leaves meeting {meeting_id}")
        return True

    async def get_meeting_participants(
        self,
        meeting_id: str
    ) -> Optional[list]:
        """
        Get list of participants in a meeting.

        Args:
            meeting_id: RealtimeKit meeting ID

        Returns:
            List of participant objects or None if error
        """
        if not self._credentials_configured():
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/meetings/{meeting_id}/participants",
                    headers={
                        "Authorization": f"Bearer {self.api_token}"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("result", [])
                else:
                    logger.error(f"Failed to get participants: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error getting participants: {e}", exc_info=True)
            return None

    def _credentials_configured(self) -> bool:
        """Check if RealtimeKit credentials are configured."""
        return all([self.account_id, self.app_id, self.api_token])


# Global service instance
realtimekit_service = CloudflareRealtimeKitService()
