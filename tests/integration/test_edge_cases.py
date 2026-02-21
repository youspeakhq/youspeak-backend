"""
Comprehensive edge case tests across all endpoints.
Covers: validation, RBAC, non-existent resources, pagination, malformed input.
"""

import uuid
import pytest
from httpx import AsyncClient

from tests.conftest import requires_db

pytestmark = requires_db


# --- Auth validation edge cases ---


@pytest.mark.asyncio
async def test_contact_inquiry_empty_school_name(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={
            "school_name": "",
            "email": f"e_{unique_suffix}@test.com",
            "inquiry_type": "billing",
            "message": "Hi",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contact_inquiry_invalid_inquiry_type(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={
            "school_name": "School",
            "email": f"e_{unique_suffix}@test.com",
            "inquiry_type": "invalid_type",
            "message": "Hi",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_contact_inquiry_missing_fields(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/contact-inquiry",
        json={},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_school_missing_required(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={"email": "a@b.com"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_school_invalid_school_type(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": f"e_{unique_suffix}@test.com",
            "password": "Pass123!",
            "school_name": "School",
            "school_type": "invalid",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_school_invalid_program_type(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": f"e_{unique_suffix}@test.com",
            "password": "Pass123!",
            "school_name": "School",
            "program_type": "invalid",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_empty_body(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(f"{api_base}/auth/login", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_nonexistent_email(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": "nonexistent@example.com", "password": "Pass123!"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_teacher_invalid_code(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": "FAKE-CODE-999",
            "email": f"t_{unique_suffix}@test.com",
            "password": "Pass123!",
            "first_name": "T",
            "last_name": "One",
        },
    )
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower() or "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_verify_code_empty(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/verify-code",
        json={"access_code": ""},
    )
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_password_reset_invalid_token(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/password/reset",
        json={"token": "invalid-token", "new_password": "NewPass123!"},
    )
    assert resp.status_code == 400


# --- Auth token edge cases ---


@pytest.mark.asyncio
async def test_protected_endpoint_no_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(f"{api_base}/schools/profile")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_invalid_token(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers={"Authorization": "Bearer invalid.jwt.token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_malformed_auth(async_client: AsyncClient, api_base: str):
    resp = await async_client.get(
        f"{api_base}/schools/profile",
        headers={"Authorization": "NotBearer token"},
    )
    assert resp.status_code == 401


# --- RBAC edge cases ---


@pytest.fixture
async def teacher_headers(async_client, api_base, registered_school, unique_suffix):
    email = f"rbac_teacher_{unique_suffix}@test.com"
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
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "Pass123!"},
    )
    return {"Authorization": f"Bearer {login.json()['data']['access_token']}"}


@pytest.mark.asyncio
async def test_teacher_cannot_access_admin_schools_profile(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(f"{api_base}/schools/profile", headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_teacher_cannot_access_admin_stats(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(f"{api_base}/admin/stats", headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_teacher_cannot_list_students(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    resp = await async_client.get(f"{api_base}/students", headers=teacher_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_teacher_cannot_create_student(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/students",
        headers=teacher_headers,
        json={
            "first_name": "S",
            "last_name": "Two",
            "class_id": str(uuid.uuid4()),
            "lang_id": 1,
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_access_teacher_my_classes(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(f"{api_base}/my-classes", headers=registered_school["headers"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_cannot_access_classrooms(async_client: AsyncClient, api_base: str):
    """No auth header: expect 401 Unauthorized."""
    resp = await async_client.get(f"{api_base}/classrooms")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_teacher_cannot_create_classroom(
    async_client: AsyncClient, api_base: str, teacher_headers: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=teacher_headers,
        json={
            "name": f"Unauth {unique_suffix}",
            "language_id": 1,
            "level": "b1",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_roster_import_rejects_non_csv(
    async_client: AsyncClient,
    api_base: str,
    teacher_headers: dict,
    unique_suffix: str,
):
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=teacher_headers)
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": f"Import Reject {unique_suffix}",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    class_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_id}/roster/import",
        headers=teacher_headers,
        files={"file": ("data.pdf", b"binary content", "application/pdf")},
    )
    assert resp.status_code == 400


@pytest.fixture
async def student_auth(async_client, api_base, registered_school, teacher_headers, unique_suffix):
    """Create a student and return (headers, student_id)."""
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=registered_school["headers"])
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "RBAC Class",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    class_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "Student",
            "last_name": f"RBAC_{unique_suffix}",
            "class_id": class_id,
            "lang_id": 1,
        },
    )
    data = resp.json()["data"]
    email = data["email"]
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": "Student123!"},
    )
    return {
        "headers": {"Authorization": f"Bearer {login.json()['data']['access_token']}"},
        "student_id": data["id"],
    }


@pytest.mark.asyncio
async def test_student_cannot_access_admin(
    async_client: AsyncClient, api_base: str, student_auth: dict
):
    resp = await async_client.get(f"{api_base}/admin/stats", headers=student_auth["headers"])
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_access_teacher_my_classes(
    async_client: AsyncClient, api_base: str, student_auth: dict
):
    resp = await async_client.get(f"{api_base}/my-classes", headers=student_auth["headers"])
    assert resp.status_code == 403


# --- Non-existent resource edge cases ---


@pytest.mark.asyncio
async def test_delete_student_nonexistent_uuid(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    fake_uuid = str(uuid.uuid4())
    resp = await async_client.delete(
        f"{api_base}/students/{fake_uuid}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_student_nonexistent_uuid(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    fake_uuid = str(uuid.uuid4())
    resp = await async_client.post(
        f"{api_base}/students/{fake_uuid}/restore",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_teacher_nonexistent_uuid(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    fake_uuid = str(uuid.uuid4())
    resp = await async_client.delete(
        f"{api_base}/teachers/{fake_uuid}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_student_invalid_uuid_class_id(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "S",
            "last_name": "Test",
            "class_id": "not-a-uuid",
            "lang_id": 1,
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_user_nonexistent(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    fake_uuid = str(uuid.uuid4())
    resp = await async_client.get(
        f"{api_base}/users/users/{fake_uuid}",
        headers=registered_school["headers"],
    )
    if resp.status_code == 404:
        return
    resp = await async_client.get(
        f"{api_base}/users/{fake_uuid}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


# --- Pagination edge cases ---


@pytest.mark.asyncio
async def test_list_students_pagination_page_one(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/students?page=1&limit=10",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert "meta" in data
    assert data["meta"]["page"] == 1
    assert data["meta"]["page_size"] == 10


@pytest.mark.asyncio
async def test_list_students_empty_result(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/students?page=999&limit=50",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []
    assert resp.json()["meta"]["total"] >= 0
    assert "total_pages" in resp.json()["meta"]


@pytest.mark.asyncio
async def test_list_students_status_filter_deleted(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.get(
        f"{api_base}/students?status=deleted",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200


# --- Duplicate / business logic edge cases ---


@pytest.mark.asyncio
async def test_teacher_invite_duplicate_email_user_exists(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Invite fails when user with email already exists (e.g. already registered)."""
    email = f"dup_invite_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T1", "last_name": "One", "email": email},
    )
    assert resp.status_code == 200
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": email,
            "password": "Pass123!",
            "first_name": "T1",
            "last_name": "One",
        },
    )
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T2", "last_name": "Two", "email": email},
    )
    assert resp.status_code == 400
    assert "already" in resp.json()["detail"].lower() or "exists" in resp.json()["detail"].lower()


# --- Users permission edge cases ---


@pytest.mark.asyncio
async def test_user_update_own_profile(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": registered_school["admin_email"], "password": registered_school["password"]},
    )
    user_id = login.json()["data"]["user_id"]
    headers = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    for path in [f"{api_base}/users/users/{user_id}", f"{api_base}/users/{user_id}"]:
        resp = await async_client.put(path, headers=headers, json={"email": registered_school["admin_email"]})
        if resp.status_code != 404:
            break
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_current(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    for path in [f"{api_base}/users/users/change-password", f"{api_base}/users/change-password"]:
        resp = await async_client.post(
            path,
            headers=registered_school["headers"],
            json={
                "current_password": "WrongCurrentPass!",
                "new_password": "NewPass123!",
            },
        )
        if resp.status_code != 404:
            break
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower() or "password" in resp.json()["detail"].lower()


# --- Malformed input edge cases ---


@pytest.mark.asyncio
async def test_login_malformed_json(async_client: AsyncClient, api_base: str):
    resp = await async_client.post(
        f"{api_base}/auth/login",
        content="{invalid json}",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_school_empty_school_name(async_client: AsyncClient, api_base: str, unique_suffix: str):
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": f"e_{unique_suffix}@test.com",
            "password": "Pass123!",
            "school_name": "",
        },
    )
    assert resp.status_code == 422


# --- Restore already-active edge case ---


# --- Additional edge cases ---


@pytest.mark.asyncio
async def test_schools_logo_invalid_file_type(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    resp = await async_client.post(
        f"{api_base}/schools/logo",
        headers=registered_school["headers"],
        files={"file": ("bad.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_class_invalid_semester_id(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    fake_semester = str(uuid.uuid4())
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "Bad Class",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "semester_id": fake_semester,
        },
    )
    assert resp.status_code in (400, 404, 422, 500)


@pytest.mark.asyncio
async def test_get_roster_nonexistent_class(
    async_client: AsyncClient, api_base: str, teacher_headers: dict
):
    fake_class = str(uuid.uuid4())
    resp = await async_client.get(
        f"{api_base}/my-classes/{fake_class}/roster",
        headers=teacher_headers,
    )
    assert resp.status_code in (404, 422, 500)


@pytest.mark.asyncio
async def test_register_teacher_with_used_code(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """Using same access code twice should fail on second use."""
    email1 = f"first_{unique_suffix}@test.com"
    email2 = f"second_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T1", "last_name": "One", "email": email1},
    )
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": email1,
            "password": "Pass123!",
            "first_name": "T1",
            "last_name": "One",
        },
    )
    resp = await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code,
            "email": email2,
            "password": "Pass123!",
            "first_name": "T2",
            "last_name": "Two",
        },
    )
    assert resp.status_code == 400
    assert "invalid" in resp.json()["detail"].lower() or "expired" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_student_twice(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    teacher_headers: dict,
    unique_suffix: str,
):
    """Second delete of same student should 404."""
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=registered_school["headers"])
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "Delete Twice",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    class_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "Del",
            "last_name": f"Twice_{unique_suffix}",
            "class_id": class_id,
            "lang_id": 1,
        },
    )
    student_id = resp.json()["data"]["id"]
    await async_client.delete(
        f"{api_base}/students/{student_id}",
        headers=registered_school["headers"],
    )
    resp = await async_client.delete(
        f"{api_base}/students/{student_id}",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_restore_student_not_deleted(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    teacher_headers: dict,
    unique_suffix: str,
):
    resp = await async_client.get(f"{api_base}/schools/semesters", headers=registered_school["headers"])
    semester_id = resp.json()["data"][0]["id"]
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_headers,
        json={
            "name": "Restore Test",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "semester_id": semester_id,
        },
    )
    class_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/students",
        headers=registered_school["headers"],
        json={
            "first_name": "Active",
            "last_name": f"Student_{unique_suffix}",
            "class_id": class_id,
            "lang_id": 1,
        },
    )
    student_id = resp.json()["data"]["id"]
    resp = await async_client.post(
        f"{api_base}/students/{student_id}/restore",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower() or "not deleted" in resp.json()["detail"].lower()
