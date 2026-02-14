"""E2E tests: Full teacher and student onboarding flow."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_invites_teacher_teacher_creates_class_admin_creates_student(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """
    E2E: Admin invites teacher -> Teacher registers -> Teacher creates class ->
    Admin creates student in class -> Teacher sees student in roster.
    """
    admin_headers = registered_school["headers"]
    teacher_email = f"teacher_{registered_school['school_id'][:8]}@test.example.com"

    # 1. Admin invites teacher
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=admin_headers,
        json={
            "first_name": "Teacher",
            "last_name": "One",
            "email": teacher_email,
        },
    )
    assert resp.status_code == 200
    access_code = resp.json()["data"]["access_code"]

    # 2. Verify code
    resp = await async_client.post(
        f"{api_base}/auth/verify-code",
        json={"access_code": access_code},
    )
    assert resp.status_code == 200

    # 3. Register teacher
    resp = await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": access_code,
            "email": teacher_email,
            "password": "Teacher123!",
            "first_name": "Teacher",
            "last_name": "One",
        },
    )
    assert resp.status_code == 200

    # 4. Login as teacher
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_email, "password": "Teacher123!"},
    )
    assert resp.status_code == 200
    teacher_headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

    # 5. Get semesters
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=teacher_headers)
    assert resp.status_code == 200
    semesters = resp.json()["data"]
    assert len(semesters) > 0
    semester_id = semesters[0]["id"]

    # 6. Teacher creates class
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "Spanish 101",
            "schedule": [
                {"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}
            ],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    assert resp.status_code == 200
    class_id = resp.json()["data"]["id"]

    # 7. Admin creates student in class
    resp = await async_client.post(
        f"{api_base}/students",
        headers=admin_headers,
        json={
            "first_name": "Student",
            "last_name": "Test",
            "class_id": class_id,
            "lang_id": 1,
        },
    )
    assert resp.status_code == 200
    student_id = resp.json()["data"]["id"]

    # 8. Teacher fetches roster
    resp = await async_client.get(
        f"{api_base}/my-classes/{class_id}/roster", headers=teacher_headers
    )
    assert resp.status_code == 200
    roster = resp.json()["data"]
    assert any(str(s["id"]) == str(student_id) for s in roster)
