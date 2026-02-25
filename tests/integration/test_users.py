"""Integration tests: Users endpoints."""

import pytest
from tests.conftest import requires_db

pytestmark = requires_db
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users_admin(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """Admin can list all users in the school."""
    resp = await async_client.get(
        f"{api_base}/users",
        headers=registered_school["headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "data" in data
    assert isinstance(data["data"], list)
    assert "meta" in data


@pytest.mark.asyncio
async def test_list_users_includes_classrooms(
    async_client: AsyncClient, 
    api_base: str, 
    registered_school: dict,
    unique_suffix: str
):
    """Generic user list must include classrooms for both roles."""
    headers = registered_school["headers"]
    
    # 1. Create a classroom
    cr_resp = await async_client.post(
        f"{api_base}/classrooms",
        headers=headers,
        json={"name": f"UnifiedRoom {unique_suffix}", "language_id": 1, "level": "a1"},
    )
    assert cr_resp.status_code == 200, cr_resp.text
    classroom_id = cr_resp.json()["data"]["id"]

    # 2. Create a teacher with this classroom
    email_t = f"t_unified_{unique_suffix}@test.com"
    resp_t = await async_client.post(
        f"{api_base}/teachers",
        headers=headers,
        json={
            "first_name": "T",
            "last_name": "Unified",
            "email": email_t,
            "classroom_ids": [classroom_id]
        }
    )
    assert resp_t.status_code == 200, resp_t.text

    # 3. Create a student and enroll them in it
    resp_s = await async_client.post(
        f"{api_base}/students",
        headers=headers,
        json={
            "first_name": "S",
            "last_name": "Unified",
            "lang_id": 1
        }
    )
    assert resp_s.status_code == 200, resp_s.text
    student_id = resp_s.json()["data"]["id"]
    await async_client.post(
        f"{api_base}/classrooms/{classroom_id}/students",
        headers=headers,
        json={"student_id": student_id}
    )

    # 4. Fetch generic user list
    resp = await async_client.get(f"{api_base}/users", headers=headers)
    assert resp.status_code == 200, resp.text
    users = resp.json()["data"]
    
    # Find teacher and student
    teacher_found = next((u for u in users if u["email"] == email_t), None)
    student_found = next((u for u in users if u["id"] == student_id), None)
    
    assert teacher_found is not None
    assert student_found is not None
    
    # Assert classrooms are populated for both
    assert any(c["id"] == classroom_id for c in teacher_found["classrooms"])
    assert any(c["id"] == classroom_id for c in student_found["classrooms"])


# --- Delete my account (self-service) ---


@pytest.mark.asyncio
async def test_delete_my_account_requires_auth(async_client: AsyncClient, api_base: str):
    """DELETE /users/me without token returns 401 or 403."""
    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        json={"password": "any"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_my_account_wrong_password(
    async_client: AsyncClient, api_base: str, registered_school: dict
):
    """DELETE /users/me with wrong password returns 400."""
    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        headers=registered_school["headers"],
        json={"password": "WrongPassword123!"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json().get("detail", "").lower() or "incorrect" in resp.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_delete_my_account_success(
    async_client: AsyncClient, api_base: str, unique_suffix: str
):
    """DELETE /users/me with correct password deletes account and returns success."""
    email = f"delete_me_{unique_suffix}@test.example.com"
    password = "DeleteMePass123!"
    reg = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": email,
            "password": password,
            "school_name": f"Delete Me School {unique_suffix}",
        },
    )
    assert reg.status_code == 200, reg.text
    login = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await async_client.request(
        "DELETE",
        f"{api_base}/users/me",
        headers=headers,
        json={"password": password},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "deleted" in (data.get("message") or "").lower()

    # Same token should no longer be valid (user deleted)
    get_resp = await async_client.get(f"{api_base}/users", headers=headers)
    assert get_resp.status_code in (401, 403, 404)
