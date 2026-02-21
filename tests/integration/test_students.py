"""Integration tests: Students endpoints."""

import asyncio
import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Fixture: classroom_id
# ---------------------------------------------------------------------------

@pytest.fixture
async def classroom_id(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Create a classroom and return its id."""
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={"name": f"Room {unique_suffix}", "language_id": 1, "level": "a1"},
    )
    assert resp.status_code == 200, resp.text
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


# ---------------------------------------------------------------------------
# Classroom-in-student-list tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_students_has_classrooms_field(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student: str,
    unique_suffix: str,
):
    """Every student object in the list response must include a 'classrooms' key."""
    # Create a student so the list is non-empty
    await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "List",
            "last_name": f"Check{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    resp = await async_client.get(
        f"{api_base}/students",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    students = resp.json()["data"]
    assert len(students) >= 1
    for student in students:
        assert "classrooms" in student, f"'classrooms' key missing for student {student.get('id')}"
        assert isinstance(student["classrooms"], list)


@pytest.mark.asyncio
async def test_student_enrolled_in_classroom_appears_in_list(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student: str,
    unique_suffix: str,
):
    """
    When a student is enrolled in a classroom, the classrooms field in the
    student-list response should contain that classroom with expected keys.
    """
    headers = registered_school["headers"]

    # 0. Create classroom inline (same school, guaranteed same admin token)
    cr_resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=headers,
        json={"name": f"EnrollRoom {unique_suffix}", "language_id": 1, "level": "a1"},
    )
    assert cr_resp.status_code == 200, cr_resp.text
    classroom_id = cr_resp.json()["data"]["id"]

    # 1. Create student (class_id and lang_id are required by StudentCreate)
    create_resp = await async_client.post(
        f"{api_base}/students",
        headers=headers,
        json={
            "first_name": "Enrolled",
            "last_name": f"Student{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    student_id = create_resp.json()["data"]["id"]

    # 2. Enroll student in classroom
    enroll_resp = await async_client.post(
        f"{api_base}/classrooms/{classroom_id}/students",
        headers=headers,
        json={"student_id": student_id},
    )
    assert enroll_resp.status_code == 200, enroll_resp.text

    # 3. Fetch student list and locate our student
    list_resp = await async_client.get(f"{api_base}/students", headers=headers)
    assert list_resp.status_code == 200
    target = next((s for s in list_resp.json()["data"] if s["id"] == student_id), None)
    assert target is not None, "Created student not found in list"

    # 4. Assert classrooms field is populated correctly
    assert len(target["classrooms"]) >= 1, (
        f"Expected classrooms for student {student_id} in classroom {classroom_id}. "
        f"Got: {target['classrooms']}"
    )
    cr = target["classrooms"][0]
    assert cr["id"] == classroom_id
    assert "name" in cr
    assert "level" in cr
    assert "language_id" in cr



@pytest.mark.asyncio
async def test_student_without_classroom_has_empty_classrooms_list(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    class_id_for_student: str,
    unique_suffix: str,
):
    """
    A student not enrolled in any classroom must have classrooms: [] in the list response.
    """
    create_resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "NoRoom",
            "last_name": f"Student{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    student_id = create_resp.json()["data"]["id"]

    list_resp = await async_client.get(
        f"{api_base}/students",
        headers=registered_school["headers"],
    )
    assert list_resp.status_code == 200

    target = next((s for s in list_resp.json()["data"] if s["id"] == student_id), None)
    assert target is not None
    assert target["classrooms"] == [], (
        f"Expected empty classrooms list but got: {target['classrooms']}"
    )
