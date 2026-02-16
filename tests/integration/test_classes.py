"""Integration tests: My-classes endpoints (teacher)."""

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
        f"{api_base}/schools/semesters",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    semester_id = resp.json()["data"][0]["id"]

    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "French 101",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
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
        f"{api_base}/schools/semesters",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    semester_id = resp.json()["data"][0]["id"]
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
            "semester_id": semester_id,
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
        f"{api_base}/schools/semesters",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Class in Classroom {unique_suffix}",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
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
async def test_import_roster_csv(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
    unique_suffix: str,
):
    resp = await async_client.get(
        f"{api_base}/schools/semesters",
        headers=teacher_headers,
    )
    assert resp.status_code == 200
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Import Test {unique_suffix}",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    assert resp.status_code == 200
    class_id = resp.json()["data"]["id"]
    csv_content = b"first_name,last_name,email\nAlice,Smith,alice." + unique_suffix.encode() + b"@test.com\nBob,Jones,\n"
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_id}/roster/import",
        headers=teacher_headers,
        files={"file": ("roster.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "enrolled" in data
    assert "created" in data
    assert data["enrolled"] >= 1
