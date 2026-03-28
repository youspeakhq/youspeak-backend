import asyncio
import httpx
import uuid
import sys
import os

# Configurable for staging
BASE_URL = "https://api-staging.youspeakhq.com/api/v1"

async def test_arena_flow():
    run_id = str(uuid.uuid4())[:8]
    admin_email = f"admin_arena_{run_id}@example.com"
    teacher_email = f"teacher_arena_{run_id}@example.com"
    student_email = f"student_arena_{run_id}@example.com"
    school_name = f"Arena Test School {run_id}"
    password = "SafePassword123!"

    print(f"🚀 Starting Arena Test: {run_id}")
    print(f"📍 Target: {BASE_URL}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Register School
        print(f"\n[1] Registering School: {school_name}...")
        resp = await client.post(f"{BASE_URL}/auth/register/school", json={
            "email": admin_email,
            "password": password,
            "school_name": school_name,
            "school_type": "secondary",
            "program_type": "partnership",
            "address_country": "US",
            "address_state": "NY",
            "address_city": "New York",
            "address_zip": "10001"
        })
        if resp.status_code != 200:
            print(f"❌ Failed to register school: {resp.text}")
            return
        admin_data = resp.json()["data"]
        print(f"✅ School registered: {admin_data['school_id']}")

        # 2. Login Admin
        print("\n[2] Logging in Admin...")
        resp = await client.post(f"{BASE_URL}/auth/login", json={
            "email": admin_email,
            "password": password
        })
        admin_token = resp.json()["data"]["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 3. Invite Teacher
        print("\n[3] Inviting Teacher...")
        resp = await client.post(f"{BASE_URL}/teachers", headers=admin_headers, json={
            "first_name": "Teacher",
            "last_name": "Arena",
            "email": teacher_email
        })
        access_code = resp.json()["data"]["access_code"]
        print(f"✅ Teacher invited, code: {access_code}")

        # 4. Register Teacher
        print("\n[4] Registering Teacher account...")
        resp = await client.post(f"{BASE_URL}/auth/register/teacher", json={
            "access_code": access_code,
            "email": teacher_email,
            "password": password,
            "first_name": "Teacher",
            "last_name": "Arena"
        })
        print(f"✅ Teacher registered")

        # 5. Login Teacher
        print("\n[5] Logging in Teacher...")
        resp = await client.post(f"{BASE_URL}/auth/login", json={
            "email": teacher_email,
            "password": password
        })
        teacher_token = resp.json()["data"]["access_token"]
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}

        # 6. Get Terms and Create Class
        print("\n[6] Creating Class...")
        resp = await client.get(f"{BASE_URL}/schools/terms", headers=teacher_headers)
        term_id = resp.json()["data"][0]["id"]
        
        # Need a language ID. Try to finding one or using a default.
        # Typically seeded with 1 = English
        class_resp = await client.post(f"{BASE_URL}/my-classes", headers=teacher_headers, json={
            "name": f"Arena Class {run_id}",
            "schedule": [{"day_of_week": "Mon", "start_time": "09:00:00", "end_time": "10:00:00"}],
            "language_id": 1,
            "term_id": term_id
        })
        class_id = class_resp.json()["data"]["id"]
        print(f"✅ Class created: {class_id}")

        # 7. Create Arena
        print("\n[7] Creating Arena...")
        arena_resp = await client.post(f"{BASE_URL}/arenas", headers=teacher_headers, json={
            "class_id": class_id,
            "title": f"Test Audio Session {run_id}",
            "description": "Testing Cloudflare RealtimeKit integration",
            "start_time": "2024-01-01T10:00:00Z", # Past or future doesn't matter for creation usually
            "duration_minutes": 60,
            "criteria": [{"name": "Clarity", "weight_percentage": 100}],
            "rules": ["Be clear"]
        })
        arena_id = arena_resp.json()["data"]["id"]
        print(f"✅ Arena created: {arena_id}")

        # 8. Initialize Arena (Admission settings)
        print("\n[8] Initializing Arena...")
        await client.post(f"{BASE_URL}/arenas/{arena_id}/initialize", headers=teacher_headers, json={
            "admission_mode": "manual",
            "allow_late_join": True
        })
        print("✅ Arena initialized")

        # 9. Start Arena Session
        print("\n[9] Starting Arena Session...")
        start_resp = await client.post(f"{BASE_URL}/arenas/{arena_id}/start", headers=teacher_headers)
        if start_resp.status_code != 200:
            print(f"❌ Failed to start arena: {start_resp.text}")
            return
        print("✅ Arena Session Started")

        # 10. Request Audio Token (Teacher)
        print("\n[10] Requesting Audio Token (Teacher)...")
        token_resp = await client.get(f"{BASE_URL}/arenas/{arena_id}/audio-token", headers=teacher_headers)
        if token_resp.status_code != 200:
            print(f"❌ Failed to get audio token: {token_resp.text}")
        else:
            token_data = token_resp.json()["data"]
            print(f"✅ Audio Token Received: {token_data['token'][:20]}...")
            print(f"✅ App ID: {token_data.get('app_id')}")

        print("\n🎉 ARENA TEST SUCCESSFUL!")
        print(f"Arena ID: {arena_id}")

if __name__ == "__main__":
    asyncio.run(test_arena_flow())
