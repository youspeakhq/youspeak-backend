"""
Integration tests for Phase 4: Arena Evaluation & Publishing
Tests scoring, analytics, ratings, and publishing endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4
from datetime import datetime, timedelta, timezone

from services.arena.models_local.arena import (
    Arena,
    ArenaWaitingRoom,
    ArenaParticipant,
    ArenaReaction,
)
from services.arena.models_local.enums import ArenaStatus
from services.arena.security import create_access_token

from ..conftest import requires_db, requires_seeded_data

# All tests in this module hit core API endpoints that require a real teacher
pytestmark = requires_seeded_data


# ============================================================================
# Helpers
# ============================================================================

FAKE_CLASS_ID = "00000000-0000-0000-0000-000000000001"
FAKE_TEACHER_ID = "00000000-0000-0000-0000-000000000002"
FAKE_STUDENT_IDS = [
    "00000000-0000-0000-0000-000000000010",
    "00000000-0000-0000-0000-000000000011",
    "00000000-0000-0000-0000-000000000012",
]


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def teacher_with_live_arena(db: AsyncSession):
    """
    Create a live arena with participants directly in the arena DB.
    Users, classes, and schools are owned by core — we use fixed UUIDs
    that correspond to the mocked core API responses in conftest.
    """
    arena = Arena(
        class_id=FAKE_CLASS_ID,
        title="Live Arena Session",
        description="Test arena for evaluation",
        status=ArenaStatus.LIVE,
        session_state="live",
        start_time=_now() - timedelta(minutes=10),
        duration_minutes=30,
        arena_mode="competitive",
        judging_mode="teacher_only",
    )
    db.add(arena)
    await db.flush()

    participant_ids = []
    for i, student_id in enumerate(FAKE_STUDENT_IDS):
        waiting_room = ArenaWaitingRoom(
            arena_id=arena.id,
            student_id=student_id,
            entry_timestamp=_now() - timedelta(minutes=15),
            status="admitted",
            admitted_at=_now() - timedelta(minutes=12),
            admitted_by=FAKE_TEACHER_ID,
        )
        db.add(waiting_room)

        participant = ArenaParticipant(
            arena_id=arena.id,
            student_id=student_id,
            role="participant",
            is_speaking=False,
            total_speaking_duration_seconds=30 + (i * 10),
            engagement_score=60.0 + (i * 10),
            last_activity=_now(),
        )
        db.add(participant)
        await db.flush()
        participant_ids.append(participant.id)

        for j in range(i + 1):
            reaction = ArenaReaction(
                arena_id=arena.id,
                user_id=FAKE_STUDENT_IDS[(i + 1) % 3],
                target_participant_id=participant.id,
                reaction_type="clap" if j % 2 == 0 else "thumbs_up",
                timestamp=_now() - timedelta(seconds=30 * j),
            )
            db.add(reaction)

    await db.commit()

    token = create_access_token({"sub": FAKE_TEACHER_ID, "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "teacher_id": FAKE_TEACHER_ID,
        "headers": headers,
        "class_id": FAKE_CLASS_ID,
        "arena_id": arena.id,
        "student_ids": FAKE_STUDENT_IDS,
        "participant_ids": participant_ids,
    }

    from sqlalchemy import delete
    await db.execute(delete(ArenaReaction).where(ArenaReaction.arena_id == arena.id))
    await db.execute(delete(ArenaParticipant).where(ArenaParticipant.arena_id == arena.id))
    await db.execute(delete(ArenaWaitingRoom).where(ArenaWaitingRoom.arena_id == arena.id))
    await db.execute(delete(Arena).where(Arena.id == arena.id))
    await db.commit()


# ============================================================================
# Tests: GET /arenas/{arena_id}/scores
# ============================================================================


@requires_db
@pytest.mark.asyncio
async def test_get_arena_scores_success(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena with participants
    WHEN: Teacher requests scores
    THEN: Returns 200 with participant score cards and top performers
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    response = await async_client.get(f"{api_base}/arenas/{arena_id}/scores", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["arena_id"] == str(arena_id)
    assert data["session_state"] == "live"
    assert len(data["participants"]) == 3

    for participant in data["participants"]:
        assert "participant_id" in participant
        assert "student_id" in participant
        assert "student_name" in participant
        assert "total_speaking_duration_seconds" in participant
        assert "engagement_score" in participant
        assert "reactions_received" in participant

    assert len(data["top_performers"]) <= 3

    engagement_scores = [p["engagement_score"] for p in data["participants"]]
    assert engagement_scores == sorted(engagement_scores, reverse=True)


@requires_db
@pytest.mark.asyncio
async def test_get_arena_scores_404_when_not_found(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A non-existent arena
    WHEN: Teacher requests scores
    THEN: Returns 404
    """
    headers = teacher_with_live_arena["headers"]
    fake_arena_id = "00000000-0000-0000-0000-000000000000"

    response = await async_client.get(f"{api_base}/arenas/{fake_arena_id}/scores", headers=headers)

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@requires_db
@pytest.mark.asyncio
async def test_get_arena_scores_requires_auth(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena
    WHEN: Unauthenticated request for scores
    THEN: Returns 401
    """
    arena_id = teacher_with_live_arena["arena_id"]
    response = await async_client.get(f"{api_base}/arenas/{arena_id}/scores")
    assert response.status_code == 401


# ============================================================================
# Tests: GET /arenas/{arena_id}/analytics
# ============================================================================


@requires_db
@pytest.mark.asyncio
async def test_get_arena_analytics_success(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena with participants
    WHEN: Teacher requests analytics
    THEN: Returns 200 with detailed analytics including timelines
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    response = await async_client.get(f"{api_base}/arenas/{arena_id}/analytics", headers=headers)

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["arena_id"] == str(arena_id)
    assert data["total_participants"] == 3
    assert "session_duration_minutes" in data
    assert "participants" in data
    assert "aggregate_stats" in data

    for participant in data["participants"]:
        assert "participant_id" in participant
        assert "student_id" in participant
        assert "total_speaking_time_seconds" in participant
        assert "average_engagement_score" in participant
        assert "total_reactions_received" in participant
        assert "reaction_breakdown" in participant
        assert "reactions_timeline" in participant

    agg = data["aggregate_stats"]
    assert "total_speaking_time_seconds" in agg
    assert "average_engagement_score" in agg
    assert "total_reactions" in agg
    assert agg["total_reactions"] == 6


@requires_db
@pytest.mark.asyncio
async def test_get_arena_analytics_404_when_not_found(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A non-existent arena
    WHEN: Teacher requests analytics
    THEN: Returns 404
    """
    headers = teacher_with_live_arena["headers"]
    fake_arena_id = "00000000-0000-0000-0000-000000000000"

    response = await async_client.get(f"{api_base}/arenas/{fake_arena_id}/analytics", headers=headers)

    assert response.status_code == 404


# ============================================================================
# Tests: POST /arenas/{arena_id}/participants/{participant_id}/rate
# ============================================================================


@requires_db
@pytest.mark.asyncio
async def test_rate_participant_success(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena with participants
    WHEN: Teacher submits rating for participant
    THEN: Returns 200 with rating confirmation
    """
    arena_id = teacher_with_live_arena["arena_id"]
    participant_id = teacher_with_live_arena["participant_ids"][0]
    headers = teacher_with_live_arena["headers"]

    rating_data = {
        "criteria_scores": {"Pronunciation": 85.0, "Fluency": 75.0, "Vocabulary": 80.0},
        "overall_rating": 80.0,
        "feedback": "Great job! Keep practicing.",
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{participant_id}/rate",
        json=rating_data,
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert data["participant_id"] == str(participant_id)
    assert data["overall_rating"] == 80.0


@requires_db
@pytest.mark.asyncio
async def test_rate_participant_404_when_not_found(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena
    WHEN: Teacher rates non-existent participant
    THEN: Returns 404
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]
    fake_participant_id = "00000000-0000-0000-0000-000000000000"

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{fake_participant_id}/rate",
        json={"criteria_scores": {"Pronunciation": 85.0}, "overall_rating": 80.0},
        headers=headers,
    )

    assert response.status_code == 404


@requires_db
@pytest.mark.asyncio
async def test_rate_participant_requires_auth(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena with participants
    WHEN: Unauthenticated request to rate participant
    THEN: Returns 401
    """
    arena_id = teacher_with_live_arena["arena_id"]
    participant_id = teacher_with_live_arena["participant_ids"][0]

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{participant_id}/rate",
        json={"criteria_scores": {"Pronunciation": 85.0}, "overall_rating": 80.0},
    )

    assert response.status_code == 401


# ============================================================================
# Tests: POST /arenas/{arena_id}/publish
# ============================================================================


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_success(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A completed arena session
    WHEN: Teacher publishes results
    THEN: Returns 200 with publish confirmation and share URL
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    await async_client.post(f"{api_base}/arenas/{arena_id}/end", json={}, headers=headers)

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json={"include_ai_analysis": True, "visibility": "class"},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True
    assert data["arena_id"] == str(arena_id)
    assert "published_at" in data
    assert "share_url" in data


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_404_when_not_completed(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A live arena (not completed)
    WHEN: Teacher tries to publish
    THEN: Returns 404
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json={"include_ai_analysis": False, "visibility": "class"},
        headers=headers,
    )

    assert response.status_code == 404
    assert "not completed" in response.json()["detail"].lower()


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_with_public_visibility(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A completed arena session
    WHEN: Teacher publishes with public visibility
    THEN: Returns 200
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    await async_client.post(f"{api_base}/arenas/{arena_id}/end", json={}, headers=headers)

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json={"include_ai_analysis": True, "visibility": "public"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["success"] is True


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_requires_auth(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A completed arena
    WHEN: Unauthenticated request to publish
    THEN: Returns 401
    """
    arena_id = teacher_with_live_arena["arena_id"]

    await async_client.post(
        f"{api_base}/arenas/{arena_id}/end",
        json={},
        headers=teacher_with_live_arena["headers"],
    )

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json={"include_ai_analysis": False, "visibility": "class"},
    )

    assert response.status_code == 401
