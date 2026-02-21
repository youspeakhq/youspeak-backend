"""Integration tests: Teachers endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_teachers(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data


@pytest.mark.asyncio
async def test_create_teacher_invite(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Admin creates teacher (is_active=False); code sent via email. Teacher activates with code."""
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "New",
            "last_name": "Teacher",
            "email": f"newteacher_{unique_suffix}@test.com",
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_code" in data
    assert "teacher_id" in data


@pytest.mark.asyncio
async def test_create_teacher_with_classroom(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
    classroom_id,
):
    """Admin creates teacher and assigns to classroom."""
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "Classroom",
            "last_name": "Teacher",
            "email": f"ct_{unique_suffix}@test.com",
            "classroom_ids": [classroom_id],
        },
    )
    assert resp.status_code == 200
    teacher_id = resp.json()["data"]["teacher_id"]
    resp = await async_client.get(
        f"{api_base}/classrooms/{classroom_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["teacher_count"] >= 1


@pytest.fixture
async def classroom_id(async_client, api_base, registered_school, unique_suffix):
    """Create a classroom for teacher assignment test."""
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=registered_school["headers"],
        json={
            "name": f"Teacher Test Room {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 200
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_import_teachers_csv(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
    classroom_id,
):
    """Bulk import teachers from CSV."""
    csv_content = (
        f"first_name,last_name,email,classroom_id\n"
        f"Bulk,One,bulk1_{unique_suffix}@test.com,{classroom_id}\n"
        f"Bulk,Two,bulk2_{unique_suffix}@test.com,\n"
    ).encode("utf-8")
    resp = await async_client.post(
        f"{api_base}/teachers/import",
        headers=registered_school["headers"],
        files={"file": ("teachers.csv", csv_content, "text/csv")},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["created"] == 2
    assert "invitations" in data
    assert len(data["invitations"]) == 2


@pytest.mark.asyncio
async def test_import_teachers_csv_rejects_non_csv(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Import rejects non-CSV files."""
    resp = await async_client.post(
        f"{api_base}/teachers/import",
        headers=registered_school["headers"],
        files={"file": ("data.txt", b"not csv", "text/plain")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Classroom-in-teacher-list tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_teachers_has_classrooms_field(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """Every teacher object in the list response must include a 'classrooms' key."""
    # Create a teacher so the list is non-empty
    await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={
            "first_name": "List",
            "last_name": f"Check{unique_suffix}",
            "email": f"listcheck_{unique_suffix}@test.com",
        },
    )
    resp = await async_client.get(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    teachers = resp.json()["data"]
    assert len(teachers) >= 1
    for teacher in teachers:
        assert "classrooms" in teacher, f"'classrooms' key missing for teacher {teacher.get('id')}"
        assert isinstance(teacher["classrooms"], list)


@pytest.mark.asyncio
async def test_teacher_enrolled_in_classroom_appears_in_list(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """
    When a teacher is assigned to a classroom, the classrooms field in the
    teacher-list response should contain that classroom with expected keys.
    """
    headers = registered_school["headers"]

    # 1. Create classroom
    cr_resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=headers,
        json={"name": f"TeacherRoom {unique_suffix}", "language_id": 1, "level": "a1"},
    )
    assert cr_resp.status_code == 200, cr_resp.text
    classroom_id = cr_resp.json()["data"]["id"]

    # 2. Create teacher and assign to classroom
    email = f"assigned_{unique_suffix}@test.com"
    create_resp = await async_client.post(
        f"{api_base}/teachers",
        headers=headers,
        json={
            "first_name": "Assigned",
            "last_name": f"Teacher{unique_suffix}",
            "email": email,
            "classroom_ids": [classroom_id],
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    teacher_id = create_resp.json()["data"]["teacher_id"]

    # 3. Fetch teacher list and locate our teacher
    list_resp = await async_client.get(f"{api_base}/teachers", headers=headers)
    assert list_resp.status_code == 200
    target = next((t for t in list_resp.json()["data"] if t["id"] == teacher_id), None)
    assert target is not None, "Created teacher not found in list"

    # 4. Assert classrooms field is populated correctly
    assert len(target["classrooms"]) >= 1, (
        f"Expected classrooms for teacher {teacher_id} in classroom {classroom_id}. "
        f"Got: {target['classrooms']}"
    )
    cr = target["classrooms"][0]
    assert cr["id"] == classroom_id
    assert "name" in cr
    assert "level" in cr
    assert "language_id" in cr


@pytest.mark.asyncio
async def test_teacher_without_classroom_has_empty_classrooms_list(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    unique_suffix: str,
):
    """
    A teacher not assigned to any classroom must have classrooms: [] in the list response.
    """
    email = f"noroom_{unique_suffix}@test.com"
    create_resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "NoRoom", "last_name": "Teacher", "email": email},
    )
    assert create_resp.status_code == 200, create_resp.text
    teacher_id = create_resp.json()["data"]["teacher_id"]

    list_resp = await async_client.get(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
    )
    assert list_resp.status_code == 200

    target = next((t for t in list_resp.json()["data"] if t["id"] == teacher_id), None)
    assert target is not None
    assert target["classrooms"] == [], (
        f"Expected empty classrooms list but got: {target['classrooms']}"
    )
