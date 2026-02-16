"""Integration tests: Students endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.fixture
async def class_id_for_student(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a teacher, have them create a class, return class_id."""
    teacher_email = f"t_{unique_suffix}@test.com"
    # Admin invites teacher
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T", "last_name": "One", "email": teacher_email},
    )
    assert resp.status_code == 200
    code = resp.json()["data"]["access_code"]
    # Register teacher
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": teacher_email,
            "password": "Pass123!",
            "first_name": "T",
            "last_name": "One",
        },
    )
    # Login teacher
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_email, "password": "Pass123!"},
    )
    token = resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    # Get semesters
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=headers)
    semester_id = resp.json()["data"][0]["id"]
    # Create class
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
async def test_list_students(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/students",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_create_student(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student,
    unique_suffix: str,
):
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "Student",
            "last_name": f"Test{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "id" in data
    assert "student_number" in data
    assert data["student_number"] is not None
    assert "-" in str(data["student_number"])


@pytest.mark.asyncio
async def test_create_student_with_provided_student_id(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student,
    unique_suffix: str,
):
    """Create student with explicit student_id (human-readable)."""
    custom_id = f"2025-{unique_suffix}"
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "CustomID",
            "last_name": f"Student{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
            "student_id": custom_id,
        },
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["student_number"] == custom_id


@pytest.mark.asyncio
async def test_import_students_csv(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student,
    unique_suffix: str,
):
    """Bulk import students from CSV."""
    csv_content = (
        f"first_name,last_name,email,student_id,class_id\n"
        f"Import,One,import1_{unique_suffix}@test.com,2025-{unique_suffix[:3]},{class_id_for_student}\n"
        f"Import,Two,import2_{unique_suffix}@test.com,,,\n"
    ).encode("utf-8")
    resp = await async_client.post(
        f"{api_base}/students/import",
        headers=registered_school["headers"],
        files={"file": ("students.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] >= 1
    assert "enrolled" in data
    assert "skipped" in data


@pytest.mark.asyncio
async def test_import_students_csv_rejects_non_csv(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Import rejects non-CSV files."""
    resp = await async_client.post(
        f"{api_base}/students/import",
        headers=registered_school["headers"],
        files={"file": ("data.txt", b"not csv", "text/plain")},
    )
    assert resp.status_code == 400
