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
