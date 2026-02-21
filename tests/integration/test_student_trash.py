"""Integration tests for Student Trash feature."""

import pytest
from httpx import AsyncClient
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select

from app.models.user import User
from app.models.student_trash import StudentTrash
from app.models.enums import UserRole
from tests.conftest import requires_db

pytestmark = requires_db


@pytest.fixture
async def sample_student(
    async_client: AsyncClient, api_base: str, registered_school: dict, class_id_for_student: str, unique_suffix: str
):
    """Create a student for testing deletion."""
    headers = registered_school["headers"]
    
    # Create student
    resp = await async_client.post(
        f"{api_base}/students",
        headers=headers,
        json={
            "first_name": "Trash",
            "last_name": f"Teststudent_{unique_suffix}",
            "class_id": class_id_for_student,
            "lang_id": 1,
        },
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


@pytest.mark.asyncio
async def test_student_trash_flow(
    async_client: AsyncClient,
    api_base: str,
    registered_school: dict,
    sample_student: dict,
):
    """Test full cycle of delete, trash record creation, and restore."""
    student_id = sample_student["id"]
    headers = registered_school["headers"]
    
    # 1. DELETE student (move to trash)
    resp = await async_client.delete(f"{api_base}/students/{student_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Student moved to trash"
    
    # 2. Verify it's gone from main list
    list_resp = await async_client.get(f"{api_base}/students", headers=headers)
    assert all(s["id"] != student_id for s in list_resp.json()["data"])

    # 3. Verify it is present in the trash list
    trash_list_resp = await async_client.get(f"{api_base}/students?status=deleted", headers=headers)
    assert any(s["id"] == student_id for s in trash_list_resp.json()["data"])

    # 4. RESTORE student
    resp = await async_client.post(f"{api_base}/students/{student_id}/restore", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Student restored successfully"
    
    # 5. Verify it's back in main list
    list_resp = await async_client.get(f"{api_base}/students", headers=headers)
    assert any(s["id"] == student_id for s in list_resp.json()["data"])
    
    # 6. Verify it's gone from trash list
    trash_list_resp = await async_client.get(f"{api_base}/students?status=deleted", headers=headers)
    assert all(s["id"] != student_id for s in trash_list_resp.json()["data"])
    # 7. Delete student again to test cleanup
    resp = await async_client.delete(f"{api_base}/students/{student_id}", headers=headers)
    assert resp.status_code == 200
    
    # 8. Trigger cleanup (nothing should happen yet as not expired)
    resp = await async_client.post(f"{api_base}/students/trash/cleanup", headers=headers)
    assert resp.status_code == 200
    assert "Cleaned up 0" in resp.json()["message"]
