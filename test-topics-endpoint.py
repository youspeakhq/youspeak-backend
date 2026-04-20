#!/usr/bin/env python3
"""
Test topics endpoint with teacher account
"""

import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "https://api-staging.youspeakhq.com"
API_PREFIX = "/api/v1"

# From previous test
ADMIN_EMAIL = "test-20260327161503@staging-test.com"
ADMIN_PASSWORD = "TestPassword123!"
SCHOOL_ID = "4012cc7e-16ce-45fb-86f8-991ff72a21c6"

TEACHER_EMAIL = f"teacher-{datetime.now().strftime('%Y%m%d%H%M%S')}@staging-test.com"
TEACHER_PASSWORD = "TeacherPassword123!"


async def test_topics():
    async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
        print("=" * 60)
        print("TOPICS ENDPOINT TEST")
        print("=" * 60)

        # Step 1: Login as admin
        print("\n1. Logging in as admin...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        if response.status_code != 200:
            print(f"   ❌ Admin login failed: {response.text}")
            return

        admin_token = response.json()["data"]["access_token"]
        print(f"   ✅ Admin logged in")

        # Step 2: Invite teacher
        print(f"\n2. Inviting teacher ({TEACHER_EMAIL})...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/teachers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": TEACHER_EMAIL,
                "first_name": "Test",
                "last_name": "Teacher",
                "class_ids": []
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()["data"]
            access_code = data["access_code"]
            print(f"   ✅ Teacher invited")
            print(f"   Access Code: {access_code}")
        else:
            print(f"   ❌ Failed: {response.text}")
            return

        # Step 3: Register teacher
        print(f"\n3. Registering teacher account...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/register/teacher",
            json={
                "access_code": access_code,
                "email": TEACHER_EMAIL,
                "password": TEACHER_PASSWORD,
                "first_name": "Test",
                "last_name": "Teacher"
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Teacher registered")
        else:
            print(f"   ❌ Failed: {response.text}")
            return

        # Step 4: Login as teacher
        print(f"\n4. Logging in as teacher...")
        response = await client.post(
            f"{BASE_URL}{API_PREFIX}/auth/login",
            json={"email": TEACHER_EMAIL, "password": TEACHER_PASSWORD}
        )
        if response.status_code != 200:
            print(f"   ❌ Teacher login failed: {response.text}")
            return

        teacher_token = response.json()["data"]["access_token"]
        teacher_id = response.json()["data"]["user_id"]
        print(f"   ✅ Teacher logged in")
        print(f"   Teacher ID: {teacher_id}")

        # Step 5: Test topics endpoint
        print(f"\n5. Testing Topics Endpoint (GET /api/v1/assessments/topics)...")
        print(f"   ⏱️  This may take 30-60 seconds if curriculum service is slow...")

        import time
        start_time = time.time()

        try:
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/assessments/topics",
                headers={"Authorization": f"Bearer {teacher_token}"},
                timeout=120.0
            )
            elapsed = time.time() - start_time

            print(f"   Status: {response.status_code}")
            print(f"   Response Time: {elapsed:.2f}s")

            if response.status_code == 200:
                data = response.json()
                topics = data.get("data", [])
                print(f"   ✅ Topics loaded successfully")
                print(f"   Total Topics: {len(topics)}")
                if topics:
                    print(f"   Sample: {json.dumps(topics[0], indent=2)}")
                else:
                    print(f"   (No topics found - empty curriculum)")
            elif response.status_code == 504:
                print(f"   ❌ 504 Gateway Timeout")
                print(f"   Root Cause: Curriculum service is slow/unresponsive")
                print(f"   Curriculum URL: http://internal-youspeak-curric-int-stg-129417713.us-east-1.elb.amazonaws.com")
                print(f"   Response: {response.text}")
            elif response.status_code == 503:
                print(f"   ⚠️  503 Service Unavailable")
                print(f"   Root Cause: Curriculum service not configured")
                print(f"   Response: {response.text}")
            else:
                print(f"   ❌ Error: {response.text}")

        except httpx.TimeoutException:
            elapsed = time.time() - start_time
            print(f"   ❌ CLIENT TIMEOUT after {elapsed:.2f}s")
            print(f"   The curriculum service did not respond within 120 seconds")
        except Exception as e:
            print(f"   ERROR: {e}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_topics())
