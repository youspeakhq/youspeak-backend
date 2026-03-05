#!/usr/bin/env python3
"""Quick test script to verify curriculum GET endpoint on staging."""

import asyncio
import httpx
import sys

# Staging configuration
STAGING_URL = "https://api-staging.youspeakhq.com"
API_BASE = f"{STAGING_URL}/api/v1"

# Test credentials (use admin credentials for curriculum access)
# Get these from your staging environment
ADMIN_EMAIL = input("Enter admin email: ") if "--interactive" in sys.argv else "admin@staging.com"
ADMIN_PASSWORD = input("Enter admin password: ") if "--interactive" in sys.argv else "changeme"


async def test_get_curriculum():
    """Test GET /api/v1/curriculums/{curriculum_id} on staging."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 60)
        print("Testing Curriculum GET endpoint on staging")
        print("=" * 60)

        # Step 1: Login as admin
        print("\n[1/3] Logging in as admin...")
        try:
            login_resp = await client.post(
                f"{API_BASE}/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
            )
            if login_resp.status_code != 200:
                print(f"❌ Login failed: {login_resp.status_code}")
                print(f"Response: {login_resp.text}")
                return False

            token = login_resp.json()["data"]["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print("✅ Login successful")
        except Exception as e:
            print(f"❌ Login error: {e}")
            return False

        # Step 2: List curriculums to get a valid ID
        print("\n[2/3] Listing curriculums to find a valid ID...")
        try:
            list_resp = await client.get(
                f"{API_BASE}/curriculums",
                headers=headers,
                params={"page": 1, "page_size": 10}
            )
            if list_resp.status_code != 200:
                print(f"❌ List failed: {list_resp.status_code}")
                print(f"Response: {list_resp.text}")
                return False

            list_data = list_resp.json()
            curriculums = list_data.get("data", [])

            if not curriculums:
                print("⚠️  No curriculums found. You may need to create one first.")
                return False

            curriculum_id = curriculums[0]["id"]
            print(f"✅ Found {len(curriculums)} curriculum(s)")
            print(f"   Testing with ID: {curriculum_id}")
        except Exception as e:
            print(f"❌ List error: {e}")
            return False

        # Step 3: Get specific curriculum
        print("\n[3/3] Getting curriculum by ID...")
        try:
            get_resp = await client.get(
                f"{API_BASE}/curriculums/{curriculum_id}",
                headers=headers
            )

            print(f"\nResponse Status: {get_resp.status_code}")

            if get_resp.status_code == 200:
                print("✅ GET curriculum successful!")
                data = get_resp.json()
                curriculum = data.get("data", {})
                print("\nCurriculum Details:")
                print(f"  ID: {curriculum.get('id')}")
                print(f"  Title: {curriculum.get('title')}")
                print(f"  Status: {curriculum.get('status')}")
                print(f"  Language: {curriculum.get('language_name')}")
                print(f"  Topics: {len(curriculum.get('topics', []))}")
                return True
            else:
                print(f"❌ GET failed: {get_resp.status_code}")
                print(f"Response: {get_resp.text}")
                return False

        except Exception as e:
            print(f"❌ GET error: {e}")
            return False


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Update ADMIN_EMAIL and ADMIN_PASSWORD in this script")
    print("    with your actual staging admin credentials before running.\n")

    input("Press Enter to continue or Ctrl+C to cancel...")

    success = asyncio.run(test_get_curriculum())

    print("\n" + "=" * 60)
    if success:
        print("✅ TEST PASSED: Curriculum GET endpoint is working on staging")
    else:
        print("❌ TEST FAILED: Check the errors above")
    print("=" * 60 + "\n")

    sys.exit(0 if success else 1)
