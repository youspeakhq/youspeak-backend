import pytest
from httpx import AsyncClient
from uuid import UUID

@pytest.mark.asyncio
async def test_announcements_full_cycle(
    async_client: AsyncClient, 
    api_base: str, 
    teacher_with_class_and_students: dict
):
    """Test creating, listing, and deleting an announcement."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    
    # 1. Create Announcement
    payload = {
        "message": "Welcome to Class. This is a test announcement.",
        "type": "general",
        "class_id": class_id
    }
    resp = await async_client.post(f"{api_base}/announcements", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    announcement_id = resp.json()["data"]["id"]
    
    # 2. List Announcements
    resp = await async_client.get(f"{api_base}/announcements", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert any(a["id"] == announcement_id for a in data)
    
    # Verify author name is present
    created_a = next(a for a in data if a["id"] == announcement_id)
    assert "author_name" in created_a
    assert created_a["author_name"] is not None
    
    # 3. Delete Announcement
    resp = await async_client.delete(f"{api_base}/announcements/{announcement_id}", headers=headers)
    assert resp.status_code == 200
    
    # Verify deleted
    resp = await async_client.get(f"{api_base}/announcements", headers=headers)
    assert not any(a["id"] == announcement_id for a in resp.json()["data"])

@pytest.mark.asyncio
async def test_learning_room_report(
    async_client: AsyncClient, 
    api_base: str, 
    teacher_with_class_and_students: dict
):
    """Test retrieving the learning room report for a class."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    
    resp = await async_client.get(f"{api_base}/my-classes/{class_id}/report", headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    
    assert data["class_id"] == class_id
    assert "active_students" in data
    assert "engagement_trend" in data
    assert "session_frequency_pct" in data
    assert isinstance(data["engagement_trend"], list)

@pytest.mark.asyncio
async def test_student_performance_analytics(
    async_client: AsyncClient, 
    api_base: str, 
    teacher_with_class_and_students: dict
):
    """Test retrieving individual student analytics."""
    headers = teacher_with_class_and_students["headers"]
    class_id = teacher_with_class_and_students["class_id"]
    student_id = teacher_with_class_and_students["student_ids"][0]
    
    url = f"{api_base}/students/{student_id}/analytics?class_id={class_id}"
    resp = await async_client.get(url, headers=headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    
    assert data["student_id"] == student_id
    assert data["class_id"] == class_id
    assert "overall_score_pct" in data
    assert "topical_mastery" in data
    assert isinstance(data["topical_mastery"], dict)
    assert "awards_count" in data

@pytest.mark.asyncio
async def test_student_analytics_bola_check(
    async_client: AsyncClient, 
    api_base: str, 
    teacher_with_class_and_students: dict,
    registered_school: dict, # Used for a different teacher context if needed
    unique_suffix: str
):
    """Test that a teacher cannot access analytics for a class they don't teach."""
    # Create another teacher who doesn't have access to the first teacher's class
    from tests.conftest import teacher_headers # assuming it's available as a fixture helper
    
    # We can just create a fresh teacher with the fixture
    email = f"other_t_{unique_suffix}@test.com"
    # Admin invites teacher
    await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "Other", "last_name": "Teacher", "email": email},
    )
    # Get code from DB or just use a helper
    # For simplicity, let's use the 'registered_school' headers which are admin headers
    # to try and check BOLA if we passed a student from a class they don't own.
    
    headers_teacher_1 = teacher_with_class_and_students["headers"]
    class_id_1 = teacher_with_class_and_students["class_id"]
    student_id_1 = teacher_with_class_and_students["student_ids"][0]
    
    # Create a second teacher
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=registered_school["headers"],
        json={"first_name": "T2", "last_name": "Two", "email": f"t2_{unique_suffix}@test.com"},
    )
    code = resp.json()["data"]["access_code"]
    await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={"access_code": code, "email": f"t2_{unique_suffix}@test.com", "password": "Pass123!", "first_name": "T2", "last_name": "Two"}
    )
    resp = await async_client.post(f"{api_base}/auth/login", json={"email": f"t2_{unique_suffix}@test.com", "password": "Pass123!"})
    headers_teacher_2 = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}
    
    # Teacher 2 tries to access Teacher 1's class analytics
    url = f"{api_base}/students/{student_id_1}/analytics?class_id={class_id_1}"
    resp = await async_client.get(url, headers=headers_teacher_2)
    assert resp.status_code == 403
    assert "access" in resp.json()["detail"].lower()
