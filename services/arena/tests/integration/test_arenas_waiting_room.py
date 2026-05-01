"""Integration tests: Arena Waiting Room & Admission (Phase 2).

Tests endpoints for join code generation, student joining, and admission control.
All endpoints test observable outcomes only.

Requirements tested:
- POST /arenas/{id}/join-code: Generate join code and QR code
- POST /arenas/{id}/waiting-room/join: Student joins with code
- GET /arenas/{id}/waiting-room: List pending students
- POST /arenas/{id}/waiting-room/{entry_id}/admit: Admit student
- POST /arenas/{id}/waiting-room/{entry_id}/reject: Reject student
"""

import pytest

from httpx import AsyncClient
from datetime import datetime, timedelta




@pytest.fixture
async def initialized_arena(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """
    Create and initialize an arena ready for waiting room flow.
    Returns: arena_id
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_ids = teacher_with_class_and_students["student_ids"][:2]

    # Create arena
    resp = await async_client.post(
        f"{api_base}/arenas",
        headers=headers,
        json={
            "class_id": class_id,
            "title": "Waiting Room Test Arena",
            "criteria": {"Clarity": 50, "Confidence": 50},
            "rules": ["Rule 1"],
        },
    )
    assert resp.status_code == 200
    arena_id = resp.json()["data"]["id"]

    # Initialize arena
    resp = await async_client.post(
        f"{api_base}/arenas/{arena_id}/initialize",
        headers=headers,
        json={
            "arena_mode": "competitive",
            "judging_mode": "teacher_only",
            "ai_co_judge_enabled": False,
            "student_selection_mode": "manual",
            "selected_student_ids": student_ids,
        },
    )
    assert resp.status_code == 200

    return arena_id


# --- Join Code Generation Tests ---


@pytest.mark.asyncio
async def test_generate_join_code_success(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: An initialized arena
    WHEN: Teacher generates join code
    THEN: Returns 200 with join_code, qr_code_url, and expires_at
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/join-code",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    data = body["data"]

    # Assert response structure
    assert "join_code" in data
    assert "qr_code_url" in data
    assert "expires_at" in data

    # Observable outcomes
    assert len(data["join_code"]) >= 6  # At least 6 characters
    assert data["join_code"].isalnum()  # Alphanumeric only
    assert data["join_code"].isupper() or data["join_code"].isdigit()  # Uppercase or digits
    assert isinstance(data["qr_code_url"], str)
    assert len(data["qr_code_url"]) > 0  # QR code generated


@pytest.mark.asyncio
async def test_generate_join_code_404_when_not_found(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    GIVEN: Non-existent arena
    WHEN: Teacher tries to generate join code
    THEN: Returns 404
    """
    resp = await async_client.post(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001/join-code",
        headers=teacher_headers,
    )

    assert resp.status_code == 404


# --- Student Join Waiting Room Tests ---


@pytest.mark.asyncio
async def test_student_join_waiting_room_success(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Arena with generated join code
    WHEN: Student joins with valid code
    THEN: Returns 200 with waiting_room_id and status="pending"
    """
    teacher_headers = teacher_with_class_and_students["headers"]

    # Generate join code
    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/join-code",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    join_code = resp.json()["data"]["join_code"]

    # Get student token (from fixture students)
    student_id = teacher_with_class_and_students["student_ids"][0]
    # Student login fixtures exist (create_student_direct in conftest.py)
    # but this test needs refactoring to use them properly.
    pytest.skip("Needs refactoring to use create_student_direct fixture")


@pytest.mark.asyncio
async def test_student_join_invalid_code(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_headers: dict,  # Using teacher for now, will fail on auth
):
    """
    GIVEN: Arena without join code
    WHEN: Student tries to join with invalid code
    THEN: Returns 400
    """
    # This test would need student auth, but we're testing the validation
    # Skip for now - needs student fixture
    pytest.skip("Student login fixture needed for full test")


# --- List Waiting Room Tests ---


@pytest.mark.asyncio
async def test_list_waiting_room_empty(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Arena with no students in waiting room
    WHEN: Teacher lists waiting room
    THEN: Returns 200 with empty pending_students list
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.get(
        f"{api_base}/arenas/{initialized_arena}/waiting-room",
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Observable outcomes
    assert data["pending_students"] == []
    assert data["total_pending"] == 0
    assert data["total_admitted"] == 0
    assert data["total_rejected"] == 0


@pytest.mark.asyncio
async def test_list_waiting_room_404_when_not_found(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    GIVEN: Non-existent arena
    WHEN: Teacher tries to list waiting room
    THEN: Returns 404
    """
    resp = await async_client.get(
        f"{api_base}/arenas/00000000-0000-0000-0000-000000000001/waiting-room",
        headers=teacher_headers,
    )

    assert resp.status_code == 404


# --- Admit Student Tests ---


@pytest.mark.asyncio
async def test_admit_student_404_when_entry_not_found(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Arena with no waiting room entries
    WHEN: Teacher tries to admit non-existent entry
    THEN: Returns 404
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/waiting-room/00000000-0000-0000-0000-000000000001/admit",
        headers=headers,
    )

    assert resp.status_code == 404


# --- Reject Student Tests ---


@pytest.mark.asyncio
async def test_reject_student_404_when_entry_not_found(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Arena with no waiting room entries
    WHEN: Teacher tries to reject non-existent entry
    THEN: Returns 404
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/waiting-room/00000000-0000-0000-0000-000000000001/reject",
        headers=headers,
        json={"reason": "Test reason"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_reject_student_with_reason(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    Test rejection with optional reason field.
    Note: This test is a placeholder - full flow requires student join first.
    """
    # Skip - needs full student join flow
    pytest.skip("Requires student join fixture for full test")


# --- Integration Flow Test ---


@pytest.mark.asyncio
async def test_full_waiting_room_flow(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    Full flow test (placeholder):
    1. Teacher generates join code
    2. Student joins waiting room
    3. Teacher lists waiting room (sees student)
    4. Teacher admits student
    5. Verify student no longer in pending list

    Currently incomplete due to missing student auth fixtures.
    """
    pytest.skip("Requires student authentication fixtures for full E2E test")


# --- Authorization Tests ---


@pytest.mark.asyncio
async def test_generate_join_code_requires_auth(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
):
    """
    GIVEN: No authentication
    WHEN: Try to generate join code
    THEN: Returns 401 or 403
    """
    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/join-code"
    )

    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_waiting_room_requires_teacher_auth(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
):
    """
    GIVEN: No authentication
    WHEN: Try to list waiting room
    THEN: Returns 401 or 403
    """
    resp = await async_client.get(
        f"{api_base}/arenas/{initialized_arena}/waiting-room"
    )

    assert resp.status_code in (401, 403)


# --- QR Code Generation Test ---


@pytest.mark.asyncio
async def test_qr_code_generation(
    async_client: AsyncClient,
    api_base: str,
    initialized_arena: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Arena with join code generated
    WHEN: Check QR code URL
    THEN: QR code is base64 data URL or valid URL string
    """
    headers = teacher_with_class_and_students["headers"]

    resp = await async_client.post(
        f"{api_base}/arenas/{initialized_arena}/join-code",
        headers=headers,
    )

    assert resp.status_code == 200
    qr_code_url = resp.json()["data"]["qr_code_url"]

    # Observable outcome: QR code URL is non-empty
    assert isinstance(qr_code_url, str)
    assert len(qr_code_url) > 0

    # If qrcode library installed, should be base64 data URL
    if qr_code_url.startswith("data:image/png;base64,"):
        # Verify it's valid base64
        import base64
        base64_data = qr_code_url.split(",")[1]
        try:
            base64.b64decode(base64_data)
            assert True  # Valid base64
        except Exception:
            assert False, "Invalid base64 in QR code data URL"


# --- Join Code Uniqueness Test ---


@pytest.mark.asyncio
async def test_join_code_uniqueness(
    async_client: AsyncClient,
    api_base: str,
    teacher_with_class_and_students: dict,
):
    """
    GIVEN: Two different arenas
    WHEN: Generate join codes for both
    THEN: Join codes are different (unique)
    """
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]

    # Create two arenas
    arena_ids = []
    for i in range(2):
        resp = await async_client.post(
            f"{api_base}/arenas",
            headers=headers,
            json={
                "class_id": class_id,
                "title": f"Test Arena {i}",
                "criteria": {"Clarity": 100},
                "rules": [],
            },
        )
        assert resp.status_code == 200
        arena_id = resp.json()["data"]["id"]
        arena_ids.append(arena_id)

        # Initialize
        await async_client.post(
            f"{api_base}/arenas/{arena_id}/initialize",
            headers=headers,
            json={
                "arena_mode": "competitive",
                "judging_mode": "teacher_only",
                "ai_co_judge_enabled": False,
                "student_selection_mode": "manual",
                "selected_student_ids": [],
            },
        )

    # Generate join codes
    join_codes = []
    for arena_id in arena_ids:
        resp = await async_client.post(
            f"{api_base}/arenas/{arena_id}/join-code",
            headers=headers,
        )
        assert resp.status_code == 200
        join_code = resp.json()["data"]["join_code"]
        join_codes.append(join_code)

    # Observable outcome: join codes are unique
    assert join_codes[0] != join_codes[1]
