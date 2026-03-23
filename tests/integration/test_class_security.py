import pytest
from httpx import AsyncClient
from tests.conftest import requires_db, create_student_direct

pytestmark = requires_db

@pytest.mark.asyncio
async def test_teacher_add_student_ownership_and_school_scoping(
    async_client: AsyncClient, api_base: str, registered_school: dict, unique_suffix: str
):
    """
    Test security checks for teacher adding student to class:
    1. Success: Teacher adds student from same school to their own class.
    2. Failure: Teacher adds student to a class they don't teach.
    3. Failure: Teacher adds student from another school.
    """
    # 1. Setup School A with Teacher A and Class A
    school_a = registered_school
    teacher_a_email = f"teacher_a_{unique_suffix}@test.com"
    
    # Admin A invites Teacher A
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=school_a["headers"],
        json={"first_name": "Teacher", "last_name": "A", "email": teacher_a_email},
    )
    assert resp.status_code == 200, f"Admin A invite teacher failed: {resp.status_code} - {resp.text}"
    code_a = resp.json()["data"]["access_code"]
    
    # Register Teacher A
    resp = await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code_a,
            "email": teacher_a_email,
            "password": "Pass123!",
            "first_name": "Teacher",
            "last_name": "A",
        },
    )
    assert resp.status_code == 200, f"Register Teacher A failed: {resp.status_code} - {resp.text}"
    
    # Login Teacher A
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_a_email, "password": "Pass123!"},
    )
    assert resp.status_code == 200, f"Login Teacher A failed: {resp.status_code} - {resp.text}"
    teacher_a_token = resp.json()["data"]["access_token"]
    teacher_a_headers = {"Authorization": f"Bearer {teacher_a_token}"}
    
    # Get Term for School A
    resp = await async_client.get(f"{api_base}/schools/terms", headers=teacher_a_headers)
    assert resp.status_code == 200, f"Get Term A failed: {resp.status_code} - {resp.text}"
    term_id_a = resp.json()["data"][0]["id"]
    
    # Teacher A creates Class A
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_a_headers,
        json={
            "name": "Class A",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id_a,
        },
    )
    assert resp.status_code == 200, f"Teacher A create Class A failed: {resp.status_code} - {resp.text}"
    class_a_id = resp.json()["data"]["id"]
    
    # Admin A creates Student A (not yet in class)
    student_a = await create_student_direct(
        async_client, api_base, school_a["headers"], None, "Student", "A", f"student_a_{unique_suffix}@test.com"
    )
    student_a_id = student_a["student_id"]
    
    # 2. Setup School B with Teacher B and Class B
    # Register School B
    resp = await async_client.post(
        f"{api_base}/auth/register/school",
        json={
            "email": f"admin_b_{unique_suffix}@test.com",
            "password": "Pass123!",
            "school_name": "School B",
        },
    )
    assert resp.status_code == 200, f"Register School B failed: {resp.status_code} - {resp.text}"
    school_b_id = resp.json()["data"]["school_id"]
    
    # Login Admin B
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": f"admin_b_{unique_suffix}@test.com", "password": "Pass123!"},
    )
    assert resp.status_code == 200, f"Login Admin B failed: {resp.status_code} - {resp.text}"
    admin_b_headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}
    
    # Admin B invites Teacher B
    teacher_b_email = f"teacher_b_{unique_suffix}@test.com"
    resp = await async_client.post(
        f"{api_base}/teachers",
        headers=admin_b_headers,
        json={"first_name": "Teacher", "last_name": "B", "email": teacher_b_email},
    )
    assert resp.status_code == 200, f"Admin B invite Teacher B failed: {resp.status_code} - {resp.text}"
    code_b = resp.json()["data"]["access_code"]
    
    # Register Teacher B
    resp = await async_client.post(
        f"{api_base}/auth/register/teacher",
        json={
            "access_code": code_b,
            "email": teacher_b_email,
            "password": "Pass123!",
            "first_name": "Teacher",
            "last_name": "B",
        },
    )
    assert resp.status_code == 200, f"Register Teacher B failed: {resp.status_code} - {resp.text}"
    
    # Login Teacher B
    resp = await async_client.post(
        f"{api_base}/auth/login",
        json={"email": teacher_b_email, "password": "Pass123!"},
    )
    assert resp.status_code == 200, f"Login Teacher B failed: {resp.status_code} - {resp.text}"
    teacher_b_headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}
    
    # Get Term for School B
    resp = await async_client.get(f"{api_base}/schools/terms", headers=teacher_b_headers)
    assert resp.status_code == 200, f"Get Term B failed: {resp.status_code} - {resp.text}"
    term_id_b = resp.json()["data"][0]["id"]
    
    # Teacher B creates Class B
    resp = await async_client.post(
        f"{api_base}/my-classes",
        headers=teacher_b_headers,
        json={
            "name": "Class B",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id_b,
        },
    )
    assert resp.status_code == 200, f"Teacher B create Class B failed: {resp.status_code} - {resp.text}"
    class_b_id = resp.json()["data"]["id"]
    
    # Admin B creates Student B
    student_b = await create_student_direct(
        async_client, api_base, admin_headers=admin_b_headers, class_id=None, 
        first_name="Student", last_name="B", email=f"student_b_{unique_suffix}@test.com"
    )
    student_b_id = student_b["student_id"]

    # --- TEST CASES ---

    # CASE 1: Teacher A adds Student A to Class A (SUCCESS)
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_a_id}/roster",
        headers=teacher_a_headers,
        json={"student_id": student_a_id, "role": "student"},
    )
    assert resp.status_code == 200, f"CASE 1 FAILED: {resp.status_code} - {resp.text}"
    assert resp.json()["message"] == "Student added to class"

    # CASE 2: Teacher A adds Student A to Class B (FAILURE - 403 Forbidden)
    # Teacher A does not teach Class B
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_b_id}/roster",
        headers=teacher_a_headers,
        json={"student_id": student_a_id, "role": "student"},
    )
    assert resp.status_code == 403, f"CASE 2 FAILED: {resp.status_code} - {resp.text}"
    assert "You do not teach this class" in resp.json()["detail"]

    # CASE 3: Teacher A adds Student B to Class A (FAILURE - 400 Bad Request)
    # Student B is in School B, Teacher A/Class A is in School A
    resp = await async_client.post(
        f"{api_base}/my-classes/{class_a_id}/roster",
        headers=teacher_a_headers,
        json={"student_id": student_b_id, "role": "student"},
    )
    assert resp.status_code == 400, f"CASE 3 FAILED: {resp.status_code} - {resp.text}"
    assert "belongs to school 'School B'" in resp.json()["detail"]
