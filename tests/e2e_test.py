import asyncio
import httpx
import uuid
import sys

BASE_URL = "http://localhost:8000/api/v1"

async def main():
    run_id = str(uuid.uuid4())[:8]
    admin_email = f"admin_{run_id}@example.com"
    teacher_email = f"teacher_{run_id}@example.com"
    school_name = f"E2E School {run_id}"
    
    print(f"Starting E2E Test Run: {run_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # [1] Register School
        print(f"\n--- [1] Register School: {school_name} ---")
        resp = await client.post(f"{BASE_URL}/auth/register/school", json={
            "account_type": "school",
            "email": admin_email,
            "password": "Password123!",
            "school_name": school_name,
        })
        if resp.status_code != 200:
            print(f"FAILED: {resp.text}")
            return
        print("SUCCESS")
        
        # [2] Login Admin
        print(f"\n--- [2] Login Admin ---")
        resp = await client.post(f"{BASE_URL}/auth/login", json={
            "email": admin_email,
            "password": "Password123!"
        })
        if resp.status_code != 200:
             print(f"FAILED: {resp.text}")
             return
        admin_token = resp.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        print("SUCCESS")
        
        # [3] Invite Teacher
        print(f"\n--- [3] Invite Teacher ---")
        resp = await client.post(f"{BASE_URL}/teachers", headers=admin_headers, json={
            "first_name": "Teacher",
            "last_name": "One",
            "email": teacher_email
        })
        if resp.status_code != 200:
            print(f"FAILED: {resp.text}")
            return
        access_code = resp.json()["data"]["access_code"]
        print(f"SUCCESS: Code {access_code}")
        
        # [4] Verify Code
        print(f"\n--- [4] Verify Code ---")
        resp = await client.post(f"{BASE_URL}/auth/verify-code", json={"access_code": access_code})
        if resp.status_code != 200:
            print(f"FAILED: {resp.text}")
            return
        print("SUCCESS")
        
        # [5] Register Teacher
        print(f"\n--- [5] Register Teacher ---")
        resp = await client.post(f"{BASE_URL}/auth/register/teacher", json={
            "access_code": access_code,
            "email": teacher_email,
            "password": "Password123!",
            "first_name": "Teacher",
            "last_name": "One"
        })
        if resp.status_code != 200:
             print(f"FAILED: {resp.text}")
             return
        print("SUCCESS")
        
        # [6] Login Teacher
        print(f"\n--- [6] Login Teacher ---")
        resp = await client.post(f"{BASE_URL}/auth/login", json={
            "email": teacher_email,
            "password": "Password123!"
        })
        if resp.status_code != 200:
             print(f"FAILED: {resp.text}")
             return
        teacher_token = resp.json()["data"]["access_token"]
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        print("SUCCESS")
        
        # [7] Create Class
        print(f"\n--- [7] Create Class ---")
        # Get Semesters
        resp = await client.get(f"{BASE_URL}/schools/semesters", headers=teacher_headers)
        if resp.status_code != 200:
             print(f"FAILED to get semesters: {resp.text}")
             return
        semesters = resp.json()["data"]
        if not semesters:
             print("FAILED: No semesters found")
             return
        semester_id = semesters[0]["id"]
        
        # Create Class
        # Assumption: Language ID 1 exists (seeded)
        class_payload = {
            "name": "Math 101",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1, 
            "semester_id": semester_id,
        }
        resp = await client.post(f"{BASE_URL}/my-classes", headers=teacher_headers, json=class_payload)
        
        if resp.status_code != 200:
             print(f"FAILED Create Class: {resp.text}")
             return
        class_id = resp.json()["data"]["id"]
        print(f"SUCCESS: Class {class_id}")
        
        # [8] Create Student (Admin)
        print(f"\n--- [8] Create Student ---")
        resp = await client.post(f"{BASE_URL}/students", headers=admin_headers, json={
            "first_name": "Student",
            "last_name": "Test",
            "class_id": class_id,
            "lang_id": 1 
        })
        if resp.status_code != 200:
             print(f"FAILED Create Student: {resp.text}")
             return
        student_id = resp.json()["data"]["id"]
        print(f"SUCCESS: Student {student_id}")
        
        # [9] Verify Roster (Teacher)
        print(f"\n--- [9] Verify Roster ---")
        resp = await client.get(f"{BASE_URL}/my-classes/{class_id}/roster", headers=teacher_headers)
        if resp.status_code != 200:
             print(f"FAILED Get Roster: {resp.text}")
             return
        roster = resp.json()["data"]
        found = any(s["id"] == student_id for s in roster)
        if not found:
             print(f"FAILED: Student not found in roster. Roster: {roster}")
             return
        print("SUCCESS: Student found in roster")
        
    print("\n✅ E2E TEST PASSED!")

if __name__ == "__main__":
    asyncio.run(main())
