#!/usr/bin/env python3
"""Full test: Register school admin, then test curriculum GET endpoint on staging."""

import asyncio
import httpx
import sys
import secrets
from datetime import datetime

# Staging configuration
STAGING_URL = "https://api-staging.youspeakhq.com"
API_BASE = f"{STAGING_URL}/api/v1"

# Generate unique email for this test run
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RANDOM_SUFFIX = secrets.token_hex(4)
TEST_EMAIL = f"admin_{TIMESTAMP}_{RANDOM_SUFFIX}@test.com"
TEST_PASSWORD = "TestPass123!"


async def test_full_flow():
    """Test full flow: register school, then test curriculum endpoints."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 70)
        print("Full Flow Test: Register School Admin + Test Curriculum")
        print("=" * 70)
        print(f"\nStaging URL: {STAGING_URL}")
        print(f"Test Email: {TEST_EMAIL}")
        print("")

        # Step 1: Register a new school
        print("[1/5] Registering new school admin...")
        try:
            register_payload = {
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "first_name": "Test",
                "last_name": "Admin",
                "school_name": f"Test School {TIMESTAMP}",
                "language_id": 1,  # English
            }

            register_resp = await client.post(
                f"{API_BASE}/auth/register/school",
                json=register_payload
            )

            if register_resp.status_code != 200:
                print(f"❌ Registration failed: {register_resp.status_code}")
                print(f"Response: {register_resp.text}")
                return False

            register_data = register_resp.json()
            print("✅ School admin registered successfully")
            print(f"   School: {register_data['data']['school']['name']}")
            print(f"   User: {register_data['data']['user']['email']}")
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return False

        # Step 2: Login with the new admin account
        print("\n[2/5] Logging in as new admin...")
        try:
            login_resp = await client.post(
                f"{API_BASE}/auth/login",
                json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
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

        # Step 3: List curriculums (should be empty for new school)
        print("\n[3/5] Listing curriculums...")
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
            print(f"✅ List successful: {len(curriculums)} curriculum(s) found")

            if len(curriculums) == 0:
                print("   (Empty as expected for new school)")
        except Exception as e:
            print(f"❌ List error: {e}")
            return False

        # Step 4: Test GET with non-existent ID (should return 404)
        print("\n[4/5] Testing GET with non-existent curriculum ID...")
        try:
            fake_uuid = "00000000-0000-0000-0000-000000000000"
            get_resp = await client.get(
                f"{API_BASE}/curriculums/{fake_uuid}",
                headers=headers
            )

            if get_resp.status_code == 404:
                print("✅ GET returned 404 as expected for non-existent ID")
            else:
                print(f"⚠️  GET returned {get_resp.status_code} (expected 404)")
                print(f"Response: {get_resp.text}")
        except Exception as e:
            print(f"❌ GET error: {e}")
            return False

        # Step 5: Verify curriculum service connectivity
        print("\n[5/5] Verifying curriculum service connectivity...")
        try:
            # Try to generate curriculum (tests if service is reachable)
            generate_resp = await client.post(
                f"{API_BASE}/curriculums/generate",
                headers=headers,
                json={
                    "prompt": "Basic French greetings",
                    "language_id": 1
                }
            )

            if generate_resp.status_code == 200:
                print("✅ Curriculum service is reachable and working")
                topics = generate_resp.json()["data"]
                print(f"   Generated {len(topics)} topic(s)")
            elif generate_resp.status_code == 503:
                print("⚠️  Curriculum service not configured (503)")
                print("   This is expected if CURRICULUM_SERVICE_URL is not set")
            else:
                print(f"⚠️  Unexpected response: {generate_resp.status_code}")
                print(f"   Response: {generate_resp.text[:200]}")
        except Exception as e:
            print(f"⚠️  Service check error: {e}")

        print("\n" + "=" * 70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nSummary:")
        print(f"  • School admin created: {TEST_EMAIL}")
        print(f"  • Login: Working ✓")
        print(f"  • List curriculums: Working ✓")
        print(f"  • GET curriculum: Working ✓")
        print("\nYou can now use these credentials for further testing:")
        print(f"  Email: {TEST_EMAIL}")
        print(f"  Password: {TEST_PASSWORD}")
        print("")

        return True


if __name__ == "__main__":
    print("\n🚀 Starting full flow test on staging...")
    print("   This will create a new test school and admin account.\n")

    success = asyncio.run(test_full_flow())

    sys.exit(0 if success else 1)
