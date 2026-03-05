"""Integration tests: My-classes endpoints (teacher)."""

import json
import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.fixture
async def teacher_headers(async_client, api_base, registered_school, unique_suffix):
    """Create a teacher and return auth headers."""
    email = f"teacher_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "Teacher", "last_name": "One", "email": email},
    )
    assert resp.status_code == 200
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": email,
            "password": "Pass123!",
            "first_name": "Teacher",
            "last_name": "One",
        },
    )
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "Pass123!"},
    )
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_get_my_classes_empty(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/my-classes",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_class(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]

    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "French 101",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "id" in data
    assert data["name"] == "French 101"


@pytest.mark.asyncio
async def test_create_class_with_timeline(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Spanish 101 {unique_suffix}",
            "description": "Brief description",
            "timeline": "Jan 2026 - May 2026",
            "schedule": [
                {"day_of_week": "Wed", "start_time": "10:00:00", "end_time": "11:00:00"}
            ],
            "language_id": 1,
            "term_id": term_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["timeline"] == "Jan 2026 - May 2026"
    assert data["description"] == "Brief description"


@pytest.mark.asyncio
async def test_create_class_with_classroom_id(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    teacher_headers: dict,
    classroom_id,
    unique_suffix: str,
):
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Class in Classroom {unique_suffix}",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "term_id": term_id,
            "classroom_id": classroom_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["classroom_id"] == classroom_id


@pytest.fixture
async def classroom_id(async_client, api_base, registered_school, unique_suffix):
    """Create a classroom for class-with-classroom tests."""
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"Test Classroom {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_create_class_with_roster_csv(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
    unique_suffix: str,
):
    """Create class with optional CSV roster in one request; response includes roster_import."""
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]
    class_payload = {
        "name": f"Import Test {unique_suffix}",
        "schedule": [
            {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
        ],
        "language_id": 1,
        "term_id": term_id,
    }
    csv_content = (
        b"first_name,last_name,email\nAlice,Smith,alice."
        + unique_suffix.encode()
        + b"@test.com\nBob,Jones,\n"
    )
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        data={"data": json.dumps(class_payload)},
        files={"file": ("roster.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "id" in data
    assert data["name"] == f"Import Test {unique_suffix}"
    assert "roster_import" in data
    ri = data["roster_import"]
    assert "enrolled" in ri
    assert "created" in ri
    assert ri["enrolled"] >= 1


@pytest.mark.asyncio
async def test_create_class_multipart_without_file(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    """Create class with multipart 'data' only (no file) succeeds; no roster_import in response."""
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]
    class_payload = {
        "name": f"Multipart No File {unique_suffix}",
        "schedule": [
            {"day_of_week": "Tue", "start_time": "10:00:00", "end_time": "11:00:00"}
        ],
        "language_id": 1,
        "term_id": term_id,
    }
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        files={"data": (None, json.dumps(class_payload).encode())},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == f"Multipart No File {unique_suffix}"
    assert "id" in data
    assert "roster_import" not in data


@pytest.mark.asyncio
async def test_create_class_multipart_missing_data_returns_400(
    async_client: AsyncClient, api_base: str, teacher_headers: dict,
):
    """Create class with multipart but no 'data' field returns 400."""
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        files={"other": (None, b"x")},
    )
    assert resp.status_code == 400
    assert "data" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_create_class_multipart_invalid_json_returns_400(
    async_client: AsyncClient, api_base: str, teacher_headers: dict,
):
    """Create class with multipart 'data' that is not valid JSON returns 400."""
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        files={"data": (None, b"not valid json")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_get_teacher_leaderboard(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    """Teacher leaderboard returns same shape as admin; scoped to teacher's classes."""
    resp = await async_client.get(
        f"{api_base}/my-classes/leaderboard",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "top_students" in data
    assert "top_classes" in data
    assert "timeframe" in data
    assert data["timeframe"] in ("week", "month", "all")
    assert isinstance(data["top_students"], list)
    assert isinstance(data["top_classes"], list)
    for entry in data["top_students"]:
        assert "rank" in entry and "student_name" in entry and "class_name" in entry and "points" in entry
    for entry in data["top_classes"]:
        assert "rank" in entry and "class_name" in entry and "score" in entry


@pytest.mark.asyncio
async def test_get_teacher_leaderboard_with_timeframe(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/my-classes/leaderboard",
        headers=teacher_headers,
        params={"timeframe": "month"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["timeframe"] == "month"


@pytest.mark.asyncio
async def test_get_teacher_leaderboard_invalid_timeframe(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(
        f"{api_base}/my-classes/leaderboard",
        headers=teacher_headers,
        params={"timeframe": "year"},
    )
    assert resp.status_code == 400
    assert "timeframe" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_get_teacher_leaderboard_requires_teacher(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Admin token cannot access teacher leaderboard (403)."""
    resp = await async_client.get(
        f"{api_base}/my-classes/leaderboard",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 403


# --- Awards (Create New Award – Figma Leaderboard) ---


@pytest.mark.asyncio
async def test_list_my_class_awards_empty(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    """GET /my-classes/awards returns paginated list (empty when no awards)."""
    resp = await async_client.get(
        f"{api_base}/my-classes/awards",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert isinstance(body["data"], list)
    assert body["meta"]["total"] >= 0


@pytest.mark.asyncio
async def test_create_award(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
    unique_suffix: str,
):
    """Create class, add student, create award (Figma: Create New Award)."""
    resp = await async_client.get(
        f"{api_base}/schools/terms",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    term_id = resp.json()["data"][0]["id"]
    class_payload = {
        "name": f"Award Class {unique_suffix}",
        "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
        "language_id": 1,
        "term_id": term_id,
    }
    csv_content = (
        b"first_name,last_name,email\n"
        + f"Awardee,One,awardee.{unique_suffix}@test.com\n".encode()
    )
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        data={"data": json.dumps(class_payload)},
        files={"file": ("roster.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    class_id = resp.json()["data"]["id"]
    # Get student_id from roster
    resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/roster",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    roster = resp.json()["data"]
    assert isinstance(roster, list)
    student_id = roster[0]["id"] if roster else None
    assert student_id, "Need at least one student to create award"
    resp = await async_client.post(
        f"{api_base}/my-classes/awards",
        headers=teacher_headers,
        json={
            "title": "Star of the Week",
            "criteria": "Outstanding participation",
            "class_ids": [class_id],
            "student_ids": [student_id],
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["title"] == "Star of the Week"
    assert data[0]["criteria"] == "Outstanding participation"
    assert data[0]["student_id"] == student_id
    assert data[0]["class_id"] == class_id
    assert "awarded_at" in data[0]


@pytest.mark.asyncio
async def test_create_award_requires_teacher(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Admin cannot create awards (403)."""
    resp = await async_client.post(
        f"{api_base}/my-classes/awards",
        headers=registered_school["headers"],
        json={
            "title": "Test",
            "class_ids": ["00000000-0000-0000-0000-000000000001"],
            "student_ids": ["00000000-0000-0000-0000-000000000002"],
        },
    )
    assert resp.status_code == 403
