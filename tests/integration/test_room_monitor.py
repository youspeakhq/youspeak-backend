"""Integration tests: Room monitor and learning session endpoints."""

import pytest
from tests.conftest import requires_db
from httpx import AsyncClient

pytestmark = requires_db


@pytest.fixture
async def teacher_with_class(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a teacher, have them create a class, return class_id and teacher headers."""
    teacher_email = f"roommon_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "Room", "last_name": "Monitor", "email": teacher_email},
    )
    assert resp.status_code == 200, resp.text
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": teacher_email,
            "password": "Pass123!",
            "first_name": "Room",
            "last_name": "Monitor",
        },
    )
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_email, "password": "Pass123!"},
    )
    assert resp.status_code == 200, resp.text
    headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}
    resp = await async_client.get(f"{api_base}/schools/terms", headers=headers)
    terms = resp.json().get("data", [])
    assert terms, "Need at least one semester"
    term_id = terms[0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=headers,
        json={
            "name": f"Monitor Class {unique_suffix}",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200, resp.text
    class_id = resp.json()["data"]["id"]
    return {"class_id": class_id, "headers": headers}


@pytest.mark.asyncio
async def test_list_room_monitor_cards(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/monitor returns one card per class (Figma: row of class cards)."""
    headers = teacher_with_class["headers"]
    class_id = teacher_with_class["class_id"]
    resp = await async_client.get(f"{api_base}/my-classes/monitor", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    cards = data["data"]
    assert isinstance(cards, list)
    assert len(cards) >= 1
    our = next((c for c in cards if c["class_id"] == class_id), None)
    assert our is not None
    assert our["class_name"]
    assert "student_count" in our
    assert "active_session" in our


@pytest.mark.asyncio
async def test_get_room_monitor_stats(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/monitor/stats returns KPIs (total_sessions, active_students, avg_session_duration_minutes)."""
    headers = teacher_with_class["headers"]
    resp = await async_client.get(
        f"{api_base}/my-classes/monitor/stats",
        headers=headers,
        params={"timeframe": "week"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    s = data["data"]
    assert "total_sessions" in s
    assert "active_students" in s
    assert "avg_session_duration_minutes" in s
    assert isinstance(s["total_sessions"], int)
    assert isinstance(s["active_students"], int)
    resp_all = await async_client.get(
        f"{api_base}/my-classes/monitor/stats",
        headers=headers,
        params={"timeframe": "all"},
    )
    assert resp_all.status_code == 200, resp_all.text
    resp_bad = await async_client.get(
        f"{api_base}/my-classes/monitor/stats",
        headers=headers,
        params={"timeframe": "invalid"},
    )
    assert resp_bad.status_code == 400, resp_bad.text


@pytest.mark.asyncio
async def test_get_room_monitor_summary(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/monitor/summary returns Class Performance Summary rows (Figma table)."""
    headers = teacher_with_class["headers"]
    class_id = teacher_with_class["class_id"]
    resp = await async_client.get(
        f"{api_base}/my-classes/monitor/summary",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    rows = data["data"]
    assert isinstance(rows, list)
    assert len(rows) >= 1
    our = next((r for r in rows if r["class_id"] == class_id), None)
    assert our is not None
    assert our["class_name"]
    assert "student_count" in our
    assert "module_progress_pct" in our
    assert "avg_quiz_score_pct" in our
    assert "time_spent_minutes_per_student" in our
    assert "last_activity_at" in our
    assert "active_session" in our


@pytest.mark.asyncio
async def test_get_room_monitor_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/{class_id}/monitor returns class info, performance summary, no active session when none."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/monitor",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    d = data["data"]
    assert d["class_id"] == class_id
    assert "class_name" in d
    assert "student_count" in d
    assert d["student_count"] >= 0
    assert "active_session" in d
    assert d["active_session"] is None
    assert "performance_summary" in d
    ps = d["performance_summary"]
    assert "recent_sessions_count" in ps
    assert "recent_sessions" in ps
    assert isinstance(ps["recent_sessions"], list)


@pytest.mark.asyncio
async def test_get_room_monitor_404_for_unknown_class(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/{class_id}/monitor returns 404 for non-existent class."""
    import uuid
    headers = teacher_with_class["headers"]
    fake_id = uuid.uuid4()
    resp = await async_client.get(
        f"{api_base}/my-classes/{fake_id}/monitor",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_room_monitor_401_without_auth(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/{class_id}/monitor returns 401 without token."""
    class_id = teacher_with_class["class_id"]
    resp = await async_client.get(f"{api_base}/my-classes/{class_id}/monitor")
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_list_sessions_empty(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/{class_id}/sessions returns empty list when no sessions."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    assert data["data"] == []


@pytest.mark.asyncio
async def test_start_session_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """POST /my-classes/{class_id}/sessions starts a session and returns it."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "learning"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("success") is True
    s = data["data"]
    assert "id" in s
    assert s["class_id"] == class_id
    assert s["session_type"] == "learning"
    assert s["status"] == "in_progress"
    assert "started_at" in s
    assert s.get("ended_at") is None


@pytest.mark.asyncio
async def test_start_second_session_fails_while_active(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """Only one active session per class; second start returns 400."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    resp1 = await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "learning"},
    )
    assert resp1.status_code == 200, resp1.text
    resp2 = await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "practice"},
    )
    assert resp2.status_code == 400, resp2.text


@pytest.mark.asyncio
async def test_room_monitor_shows_active_session(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """After starting a session, GET monitor returns active_session populated."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    start_resp = await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "practice"},
    )
    assert start_resp.status_code == 200, start_resp.text
    session_id = start_resp.json()["data"]["id"]

    monitor_resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/monitor",
        headers=headers,
    )
    assert monitor_resp.status_code == 200, monitor_resp.text
    d = monitor_resp.json()["data"]
    assert d["active_session"] is not None
    assert d["active_session"]["id"] == session_id
    assert d["active_session"]["status"] == "in_progress"


@pytest.mark.asyncio
async def test_end_session_success(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """PATCH /my-classes/{class_id}/sessions/{session_id} ends the session."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    start_resp = await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "learning"},
    )
    assert start_resp.status_code == 200, start_resp.text
    session_id = start_resp.json()["data"]["id"]

    end_resp = await async_client.patch(
        f"{api_base}/my-classes/{class_id}/sessions/{session_id}",
        headers=headers,
    )
    assert end_resp.status_code == 200, end_resp.text

    monitor_resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/monitor",
        headers=headers,
    )
    assert monitor_resp.status_code == 200, monitor_resp.text
    assert monitor_resp.json()["data"]["active_session"] is None


@pytest.mark.asyncio
async def test_list_sessions_after_start_and_end(
    async_client: AsyncClient, api_base: str, teacher_with_class: dict
):
    """GET /my-classes/{class_id}/sessions returns sessions with correct status."""
    class_id = teacher_with_class["class_id"]
    headers = teacher_with_class["headers"]
    await async_client.post(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
        json={"session_type": "learning"},
    )
    resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/sessions",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    sessions = resp.json()["data"]
    assert len(sessions) >= 1
    assert sessions[0]["status"] == "in_progress"
    assert sessions[0]["session_type"] == "learning"
