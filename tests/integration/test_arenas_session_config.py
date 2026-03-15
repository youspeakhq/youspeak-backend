"""Integration tests: Arena Session Configuration (Phase 1).

Tests endpoints for initializing arena sessions with student selection.
All endpoints require teacher auth; tests assert observable outcomes only.

Requirements tested:
- GET /students/search: Search students in class by name with pagination
- POST /arenas/{id}/initialize: Configure arena mode, judging, AI, student selection
- POST /arenas/{id}/students/randomize: Randomly select N students from class
- POST /arenas/{id}/students/hybrid: Combine manual + random student selection
"""

import pytest
from tests.conftest import requires_db
from httpx import AsyncClient

pytestmark = requires_db


@pytest.fixture
async def teacher_with_class_and_students(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """
    Create teacher, class, and 5 enrolled students for session configuration tests.
    Returns: {"headers": teacher_headers, "class_id": UUID, "student_ids": [UUID]}
    """
    # Create teacher
    teacher_email = f"arena_teacher_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "Arena", "last_name": "Teacher", "email": teacher_email},
    )
    assert resp.status_code == 200, resp.text
    code = resp.json()["data"]["access_code"]

    # Register teacher
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": teacher_email,
            "password": "Pass123!",
            "first_name": "Arena",
            "last_name": "Teacher",
        },
    )

    # Login teacher
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_email, "password": "Pass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["data"]["access_token"]
    teacher_headers = {"Authorization": f"Bearer {token}"}

    # Get terms
    resp = await async_client.get(f"{api_base}/schools/terms", headers=teacher_headers)
    terms = resp.json().get("data", [])
    assert terms, "Need at least one semester"
    term_id = terms[0]["id"]

    # Create class
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Arena Test Class {unique_suffix}",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200, resp.text
    class_id = resp.json()["data"]["id"]

    # Create 5 students enrolled in this class
    student_ids = []
    for i in range(5):
        student_email = f"student_{unique_suffix}_{i}@test.com"

        # Admin invites student
        resp = await async_client.post(
            f"{api_base}/students",
            headers=registered_school["headers"],
            json={
                "first_name": f"Student{i}",
                "last_name": "Test",
                "email": student_email,
            },
        )
        assert resp.status_code == 200, resp.text
        invite_code = resp.json()["data"]["invite_code"]

        # Register student
        resp = await async_client.post(
            f"{api_base}/auth/register/student",
            json={
                "invite_code": invite_code,
                "email": student_email,
                "password": "Pass123!",
                "first_name": f"Student{i}",
                "last_name": "Test",
            },
        )
        assert resp.status_code == 200, resp.text
        student_id = resp.json()["data"]["user_id"]
        student_ids.append(student_id)

        # Enroll student in class
        resp = await async_client.post(
            f"{api_base}/classes/{class_id}/students",
            headers=teacher_headers,
            json={"student_ids": [student_id]},
        )
        assert resp.status_code == 200, resp.text

    return {
        "headers": teacher_headers,
        "class_id": class_id,
        "student_ids": student_ids,
    }


@pytest.fixture
async def arena_draft(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """Create a draft arena for testing session configuration."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "Test Arena for Session Config",
            "description": "Test arena",
            "criteria": {"Clarity": 40, "Confidence": 30, "Grammar": 30},
            "rules": ["Rule 1", "Rule 2"],
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


# --- Student Search Endpoint Tests ---


@pytest.mark.asyncio
async def test_search_students_success(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 enrolled students
    WHEN: Teacher searches students in that class
    THEN: Returns 200 with list of students
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.get(
        f"{api_base}/arenas/students/search?class_id={class_id}",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    # Assert response structure
    assert "students" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data

    # Assert observable outcome: 5 students returned
    assert data["total"] == 5
    assert len(data["students"]) == 5

    # Assert student structure
    for student in data["students"]:
        assert "id" in student
        assert "name" in student
        assert "avatar_url" in student
        assert "status" in student


@pytest.mark.asyncio
async def test_search_students_with_name_filter(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with students named Student0, Student1, etc.
    WHEN: Teacher searches with name filter "Student1"
    THEN: Returns only matching students
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.get(
        f"{api_base}/arenas/students/search?class_id={class_id}&name=Student1",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: Only Student1 matches
    assert data["total"] >= 1
    for student in data["students"]:
        assert "Student1" in student["name"]


@pytest.mark.asyncio
async def test_search_students_pagination(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher requests page_size=2
    THEN: Returns 2 students per page, correct total
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.get(
        f"{api_base}/arenas/students/search?class_id={class_id}&page=1&page_size=2",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcomes
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] == 5
    assert len(data["students"]) == 2  # First page has 2 students


@pytest.mark.asyncio
async def test_search_students_forbidden_when_not_teaching_class(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    GIVEN: A teacher who doesn't teach a specific class
    WHEN: Teacher tries to search students in that class
    THEN: Returns 403 Forbidden
    """
    # Use random UUID that teacher doesn't teach
    resp = await async_client.get(
        f"{api_base}/arenas/students/search?class_id=00000000-0000-0000-0000-000000000099",
        headers=teacher_headers,
    )

    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_search_students_requires_auth(
    async_client: AsyncClient,
    api_base: str,
):
    """
    GIVEN: No authentication
    WHEN: Request student search
    THEN: Returns 401 or 403
    """
    resp = await async_client.get(
        f"{api_base}/arenas/students/search?class_id=00000000-0000-0000-0000-000000000001"
    )

    assert resp.status_code in (401, 403)


# --- Arena Initialize Endpoint Tests ---


@pytest.mark.asyncio
async def test_initialize_arena_competitive_mode_success(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A draft arena and selected students
    WHEN: Teacher initializes with competitive mode + manual selection
    THEN: Returns 200, session_state="initialized", configuration saved
    """
    headers = teacher_with_class_and_students["headers"]
    student_ids = teacher_with_class_and_students["student_ids"][:2]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/initialize",
        headers=headers,
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    # Assert response structure and observable outcomes
    assert data["session_id"] == arena_draft
    assert data["status"] == "initialized"
    assert len(data["participants"]) == 2

    # Assert configuration
    config = data["configuration"]
    assert config["arena_mode"] == "competitive"
    assert config["judging_mode"] == "teacher_only"
    assert config["ai_co_judge_enabled"] is False
    assert config["student_selection_mode"] == "manual"

    # Verify database state by fetching arena again
    get_resp = await async_client.get(
        f"{api_base}/arenas/{arena_draft}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    # Note: ArenaResponse doesn't include new fields yet,
    # but we verified via initialize response that they were saved


@pytest.mark.asyncio
async def test_initialize_arena_collaborative_mode_success(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A draft arena
    WHEN: Teacher initializes with collaborative mode + team_size
    THEN: Returns 200, configuration includes team_size
    """
    headers = teacher_with_class_and_students["headers"]
    student_ids = teacher_with_class_and_students["student_ids"][:4]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "hybrid",
            "ai_co_judge_enabled": True,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            "team_size": 2,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    config = data["configuration"]
    assert config["arena_mode"] == "collaborative"
    assert config["judging_mode"] == "hybrid"
    assert config["ai_co_judge_enabled"] is True
    assert config["team_size"] == 2


@pytest.mark.asyncio
async def test_initialize_arena_validation_team_size_required_for_collaborative(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Collaborative mode without team_size
    WHEN: Teacher initializes arena
    THEN: Returns 422 validation error (team_size required)
    """
    headers = teacher_with_class_and_students["headers"]
    student_ids = teacher_with_class_and_students["student_ids"][:2]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            # Missing team_size
        },
    )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_initialize_arena_validation_team_size_range(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: team_size outside valid range (2-5)
    WHEN: Teacher initializes arena
    THEN: Returns 422 validation error
    """
    headers = teacher_with_class_and_students["headers"]
    student_ids = teacher_with_class_and_students["student_ids"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/initialize",
        headers=headers,
        json={
            "arena_mode": "collaborative",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
            "team_size": 10,  # Invalid: must be 2-5
        },
    )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_initialize_arena_validation_manual_mode_requires_students(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Manual selection mode with empty selected_student_ids
    WHEN: Teacher initializes arena
    THEN: Returns 422 validation error
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/initialize",
        headers=headers,
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": [],  # Empty - should fail validation
        },
    )

    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_initialize_arena_404_when_not_found(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    GIVEN: Non-existent arena ID
    WHEN: Teacher tries to initialize
    THEN: Returns 404
    """
    resp = await async_client.post(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001/initialize",
        headers=teacher_headers,
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": ["00000000-0000-0000-0000-000000000002"],
        },
    )

    assert resp.status_code == 404, resp.text


# --- Randomize Students Endpoint Tests ---


@pytest.mark.asyncio
async def test_randomize_students_success(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher requests randomize 3 students
    THEN: Returns 200 with exactly 3 students
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/randomize",
        headers=headers,
        json={
            "class_id": class_id,
            "participant_count": 3,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: exactly 3 students selected
    assert len(data["selected_students"]) == 3

    # All students should have required fields
    for student in data["selected_students"]:
        assert "id" in student
        assert "name" in student


@pytest.mark.asyncio
async def test_randomize_students_all_when_count_exceeds_available(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher requests randomize 10 students (more than available)
    THEN: Returns all 5 students
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/randomize",
        headers=headers,
        json={
            "class_id": class_id,
            "participant_count": 10,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: returns all available students (5)
    assert len(data["selected_students"]) == 5


@pytest.mark.asyncio
async def test_randomize_students_forbidden_when_not_teaching_class(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_headers: dict,
):
    """
    GIVEN: A teacher who doesn't teach the class
    WHEN: Teacher tries to randomize students
    THEN: Returns 403 Forbidden
    """
    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/randomize",
        headers=teacher_headers,
        json={
            "class_id": "00000000-0000-0000-0000-000000000099",
            "participant_count": 3,
        },
    )

    assert resp.status_code == 403, resp.text


# --- Hybrid Selection Endpoint Tests ---


@pytest.mark.asyncio
async def test_hybrid_selection_success(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher selects 2 manually and requests 2 random
    THEN: Returns 4 students total (2 manual + 2 random)
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"]

    # Manually select first 2 students
    manual_selections = student_ids[:2]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/hybrid",
        headers=headers,
        json={
            "class_id": class_id,
            "manual_selections": manual_selections,
            "randomize_count": 2,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: 4 students total (2 manual + 2 random)
    assert len(data["final_participants"]) == 4

    # Verify manual selections are included
    selected_ids = [s["id"] for s in data["final_participants"]]
    assert manual_selections[0] in selected_ids
    assert manual_selections[1] in selected_ids


@pytest.mark.asyncio
async def test_hybrid_selection_only_manual(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher selects 3 manually and requests 0 random
    THEN: Returns exactly 3 students (the manual selections)
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"]

    manual_selections = student_ids[:3]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/hybrid",
        headers=headers,
        json={
            "class_id": class_id,
            "manual_selections": manual_selections,
            "randomize_count": 0,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: exactly 3 students (manual only)
    assert len(data["final_participants"]) == 3


@pytest.mark.asyncio
async def test_hybrid_selection_only_random(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: A class with 5 students
    WHEN: Teacher selects 0 manually and requests 3 random
    THEN: Returns 3 random students
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/hybrid",
        headers=headers,
        json={
            "class_id": class_id,
            "manual_selections": [],
            "randomize_count": 3,
        },
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcome: exactly 3 students (random only)
    assert len(data["final_participants"]) == 3


@pytest.mark.asyncio
async def test_hybrid_selection_forbidden_when_not_teaching_class(
    async_client: AsyncClient,
    api_base: str,
    arena_draft: str,
    teacher_headers: dict,
):
    """
    GIVEN: A teacher who doesn't teach the class
    WHEN: Teacher tries hybrid selection
    THEN: Returns 403 Forbidden
    """
    resp = await async_client.post(
        f"{api_base}/arenas/{arena_draft}/students/hybrid",
        headers=teacher_headers,
        json={
            "class_id": "00000000-0000-0000-0000-000000000099",
            "manual_selections": [],
            "randomize_count": 2,
        },
    )

    assert resp.status_code == 403, resp.text
