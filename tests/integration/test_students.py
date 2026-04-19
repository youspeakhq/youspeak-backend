"""Integration tests: Students endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


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


@pytest.mark.asyncio
async def test_teacher_can_list_students(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
):
    """
    Teachers should be able to list all students in their school.
    This tests the authorization fix that changed require_admin to require_teacher_or_admin.
    """
    list_resp = await async_client.get(
        f"{api_base}/students",
        headers=teacher_headers,
    )
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()
    assert "data" in data
    assert "meta" in data
    assert isinstance(data["data"], list)
