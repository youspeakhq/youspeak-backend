"""
Integration tests for Phase 4: Arena Evaluation & Publishing
Tests scoring, analytics, ratings, and publishing endpoints.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, timedelta

from app.models.user import User
from app.models.arena import Arena, ArenaWaitingRoom, ArenaParticipant, ArenaReaction
from app.models.academic import Class
from app.models.enums import UserRole, ArenaStatus
from app.core.security import create_access_token
from tests.conftest import requires_db


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def teacher_with_live_arena(async_client: AsyncClient, db: AsyncSession):
    """
    Create teacher with a live arena session that has admitted participants.
    Returns: dict with teacher_id, headers, class_id, arena_id, participant_ids
    """
    # Create a fake school first
    from app.models.onboarding import School
    from app.models.enums import SchoolType, ProgramType
    fake_school_id = UUID("00000000-0000-0000-0000-000000000001")
    school = School(
        id=fake_school_id,
        name="Test School",
        school_type=SchoolType.PRIMARY,
        program_type=ProgramType.PIONEER
    )
    db.add(school)
    await db.flush()

    # Create teacher with school_id
    teacher = User(
        email="teacher@test.com",
        first_name="Teacher",
        last_name="Test",
        role=UserRole.TEACHER,
        hashed_password="fake_hash",
        is_active=True,
        language_id=1,
        school_id=fake_school_id
    )
    db.add(teacher)
    await db.flush()

    # Create term for the class
    from app.models.academic import Term
    from datetime import date
    term = Term(
        school_id=fake_school_id,
        name="Test Term 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        is_active=True
    )
    db.add(term)
    await db.flush()

    # Create class
    class_ = Class(
        name="Test Class",
        school_id=fake_school_id,
        term_id=term.id,
        language_id=1,
        description="Test class for arena"
    )
    db.add(class_)
    await db.flush()

    # Create students and enroll them
    student_ids = []
    for i in range(3):
        student = User(
            email=f"student{i}@test.com",
            first_name=f"Student",
            last_name=f"{i}",
            role=UserRole.STUDENT,
            hashed_password="fake_hash",
            is_active=True,
            language_id=1,
            school_id=fake_school_id
        )
        db.add(student)
        await db.flush()
        student_ids.append(student.id)

        # Enroll student in class
        class_.students.append(student)

    # Create arena in live state
    arena = Arena(
        class_id=class_.id,
        title="Live Arena Session",
        description="Test arena for evaluation",
        status=ArenaStatus.ACTIVE,
        session_state='live',
        start_time=datetime.utcnow() - timedelta(minutes=10),
        duration_minutes=30,
        arena_mode='competitive',
        judging_mode='teacher_only'
    )
    db.add(arena)
    await db.flush()

    # Create arena participants with some data
    participant_ids = []
    for i, student_id in enumerate(student_ids):
        # Add waiting room entry (admitted)
        waiting_room = ArenaWaitingRoom(
            arena_id=arena.id,
            student_id=student_id,
            entry_timestamp=datetime.utcnow() - timedelta(minutes=15),
            status='admitted',
            admitted_at=datetime.utcnow() - timedelta(minutes=12),
            admitted_by=teacher.id
        )
        db.add(waiting_room)

        # Add participant
        participant = ArenaParticipant(
            arena_id=arena.id,
            student_id=student_id,
            role='participant',
            is_speaking=False,
            total_speaking_duration_seconds=30 + (i * 10),  # 30, 40, 50 seconds
            engagement_score=60.0 + (i * 10),  # 60, 70, 80
            last_activity=datetime.utcnow()
        )
        db.add(participant)
        await db.flush()
        participant_ids.append(participant.id)

        # Add some reactions
        for j in range(i + 1):  # Student 0: 1 reaction, Student 1: 2, Student 2: 3
            reaction = ArenaReaction(
                arena_id=arena.id,
                user_id=student_ids[(i + 1) % 3],  # From other students
                target_participant_id=participant.id,
                reaction_type='clap' if j % 2 == 0 else 'thumbs_up',
                timestamp=datetime.utcnow() - timedelta(seconds=30 * j)
            )
            db.add(reaction)

    await db.commit()

    # Create auth token
    token = create_access_token({"sub": str(teacher.id), "type": "access"})
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "teacher_id": teacher.id,
        "headers": headers,
        "class_id": class_.id,
        "arena_id": arena.id,
        "student_ids": student_ids,
        "participant_ids": participant_ids
    }


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

    # Verify score cards have required fields
    for participant in data["participants"]:
        assert "participant_id" in participant
        assert "student_id" in participant
        assert "student_name" in participant
        assert "total_speaking_duration_seconds" in participant
        assert "engagement_score" in participant
        assert "reactions_received" in participant

    # Verify top performers are ranked by engagement score
    assert len(data["top_performers"]) <= 3

    # Verify participants are ordered by engagement score (descending)
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

    # Verify participant analytics have required fields
    for participant in data["participants"]:
        assert "participant_id" in participant
        assert "student_id" in participant
        assert "total_speaking_time_seconds" in participant
        assert "average_engagement_score" in participant
        assert "total_reactions_received" in participant
        assert "reaction_breakdown" in participant
        assert "reactions_timeline" in participant

    # Verify aggregate stats
    agg = data["aggregate_stats"]
    assert "total_speaking_time_seconds" in agg
    assert "average_engagement_score" in agg
    assert "total_reactions" in agg
    assert agg["total_reactions"] == 6  # 1 + 2 + 3 reactions


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
        "criteria_scores": {
            "Pronunciation": 85.0,
            "Fluency": 75.0,
            "Vocabulary": 80.0
        },
        "overall_rating": 80.0,
        "feedback": "Great job! Keep practicing."
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{participant_id}/rate",
        json=rating_data,
        headers=headers
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

    rating_data = {
        "criteria_scores": {"Pronunciation": 85.0},
        "overall_rating": 80.0
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{fake_participant_id}/rate",
        json=rating_data,
        headers=headers
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

    rating_data = {
        "criteria_scores": {"Pronunciation": 85.0},
        "overall_rating": 80.0
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/participants/{participant_id}/rate",
        json=rating_data
    )

    assert response.status_code == 401


# ============================================================================
# Tests: POST /arenas/{arena_id}/publish
# ============================================================================


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_success(async_client: AsyncClient, api_base: str, teacher_with_live_arena, db: AsyncSession):
    """
    GIVEN: A completed arena session
    WHEN: Teacher publishes results
    THEN: Returns 200 with publish confirmation and share URL
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    # First, end the arena session
    await async_client.post(f"{api_base}/arenas/{arena_id}/end", json={}, headers=headers)

    # Now publish
    publish_data = {
        "include_ai_analysis": True,
        "visibility": "class"
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json=publish_data,
        headers=headers
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
    THEN: Returns 404 (arena must be completed first)
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    publish_data = {
        "include_ai_analysis": False,
        "visibility": "class"
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json=publish_data,
        headers=headers
    )

    assert response.status_code == 404
    assert "not completed" in response.json()["detail"].lower()


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_with_public_visibility(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A completed arena session
    WHEN: Teacher publishes with public visibility
    THEN: Returns 200 with public share URL
    """
    arena_id = teacher_with_live_arena["arena_id"]
    headers = teacher_with_live_arena["headers"]

    # End session first
    await async_client.post(f"{api_base}/arenas/{arena_id}/end", json={}, headers=headers)

    # Publish with public visibility
    publish_data = {
        "include_ai_analysis": True,
        "visibility": "public"
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json=publish_data,
        headers=headers
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["success"] is True


@requires_db
@pytest.mark.asyncio
async def test_publish_arena_requires_auth(async_client: AsyncClient, api_base: str, teacher_with_live_arena):
    """
    GIVEN: A completed arena
    WHEN: Unauthenticated request to publish
    THEN: Returns 401
    """
    arena_id = teacher_with_live_arena["arena_id"]

    # End session first (with auth)
    await async_client.post(
        f"{api_base}/arenas/{arena_id}/end",
        json={},
        headers=teacher_with_live_arena["headers"]
    )

    # Try to publish without auth
    publish_data = {
        "include_ai_analysis": False,
        "visibility": "class"
    }

    response = await async_client.post(
        f"{api_base}/arenas/{arena_id}/publish",
        json=publish_data
    )

    assert response.status_code == 401
