"""Integration tests: Classroom endpoints (Admin)."""

import uuid
import pytest
from httpx import AsyncClient

from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
async def classroom_id(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a classroom and return its ID."""
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"AP Chinese {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


@pytest.fixture
async def teacher_id_and_headers(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a teacher, return (teacher_id, headers)."""
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
    data = resp.json()["data"]
    teacher_id = data.get("user_id")
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return teacher_id, headers


@pytest.fixture
async def class_id_for_student(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create teacher + class, return class_id."""
    email = f"t_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T", "last_name": "One", "email": email},
    )
    assert resp.status_code == 200
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": email,
            "password": "Pass123!",
            "first_name": "T",
            "last_name": "One",
        },
    )
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "Pass123!"},
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=headers)
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=headers,
        json={
            "name": "Test Class",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_list_classrooms_empty(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_create_classroom(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"AP Chinese Language {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "id" in data
    assert data["name"] == f"AP Chinese Language {unique_suffix}"
    assert data["language_id"] == 1
    assert data["level"] == "b1"
    assert "school_id" in data


@pytest.mark.asyncio
async def test_create_classroom_all_levels(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    levels = ["beginner", "a1", "a2", "b1", "b2", "intermediate", "c1"]
    for level in levels:
        resp = await async_client.post(
            f"{api_base}/classrooms",
            headers=registered_school["headers"],
            json={
                "name": f"Class {level} {unique_suffix}",
                "language_id": 1,
                "level": level,
            },
        )
        assert resp.status_code == 200, f"Level {level}: {resp.text}"


@pytest.mark.asyncio
async def test_get_classroom(
    async_client: AsyncClient, api_base: str, registered_school: dict, classroom_id
):
    resp = await async_client.get(
        f"{api_base}/classrooms/{classroom_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == classroom_id
    assert "teacher_count" in data
    assert "student_count" in data
    assert data["teacher_count"] >= 0
    assert data["student_count"] >= 0


@pytest.mark.asyncio
async def test_get_classroom_not_found(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    fake_id = str(uuid.uuid4())
    resp = await async_client.get(
        f"{api_base}/classrooms/{fake_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_classrooms_after_create(
    async_client: AsyncClient, api_base: str, registered_school: dict, classroom_id
):
    resp = await async_client.get(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    ids = [c["id"] for c in data]
    assert classroom_id in ids


@pytest.mark.asyncio
async def test_teacher_cannot_create_classroom(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=teacher_headers,
        json={
            "name": f"Unauthorized {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 403


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
async def test_add_teacher_to_classroom(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    classroom_id,
    teacher_id_and_headers,
):
    teacher_id, _ = teacher_id_and_headers
    if not teacher_id:
        pytest.skip("Could not resolve teacher_id from login response")
    resp = await async_client.post(
        f"{api_base}/classrooms/{classroom_id}/teachers",
        headers=registered_school["headers"],
        json={"teacher_id": str(teacher_id)},
    )
    assert resp.status_code == 200
    resp = await async_client.get(
        f"{api_base}/classrooms/{classroom_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["teacher_count"] >= 1


@pytest.mark.asyncio
async def test_add_student_to_classroom(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    classroom_id,
    class_id_for_student,
    unique_suffix: str,
):
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "RoomStudent",
            "last_name": f"X{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    assert resp.status_code == 200
    student_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/classrooms/{classroom_id}/students",
        headers=registered_school["headers"],
        json={"student_id": str(student_id)},
    )
    assert resp.status_code == 200
    resp = await async_client.get(
        f"{api_base}/classrooms/{classroom_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["student_count"] >= 1


@pytest.mark.asyncio
async def test_create_classroom_invalid_level(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"Bad {unique_suffix}",
            "language_id": 1,
            "level": "invalid_level",
        },
    )
    assert resp.status_code == 422
