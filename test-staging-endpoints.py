#!/usr/bin/env python3
"""
Test staging endpoints:
1. Register account
2. Test /api/v1/assessments/topics endpoint
3. Test /api/v1/arenas/{arena_id}/audio/token endpoint
"""

import asyncio
import httpx
import json
from datetime import datetime
from uuid import uuid4

BASE_URL = "https://youspeak-alb-staging-620291408.us-east-1.elb.amazonaws.com"
API_PREFIX = "/api/v1"

# Test data
TEST_EMAIL = f"test-{datetime.now().strftime('%Y%m%d%H%M%S')}@staging-test.com"
TEST_PASSWORD = "TestPassword123!"
TEST_SCHOOL_NAME = f"Test School {datetime.now().strftime('%Y%m%d%H%M%S')}"


async def test_staging():
    """Test staging endpoints"""

    # Disable SSL verification for ALB testing (staging uses self-signed cert)
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        print("=" * 60)
        print("STAGING ENDPOINT TESTING")
        print("=" * 60)

        # Step 1: Health check
        print("\n1. Health Check...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   Response: {response.json()}")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   ERROR: {e}")
            return

        # Step 2: Register school account
        print(f"\n2. Registering School Account...")
        print(f"   Email: {TEST_EMAIL}")
        print(f"   School: {TEST_SCHOOL_NAME}")

        try:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/register/school",
                json={
                    "school_name": TEST_SCHOOL_NAME,
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD,
                    "school_type": "primary",
                    "program_type": "pioneer",
                    "timezone": "America/New_York",
                    "country": "United States"
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ Account created successfully")
                print(f"   Response: {json.dumps(response.json(), indent=2)}")
            else:
                print(f"   ❌ Registration failed: {response.text}")
                return
        except Exception as e:
            print(f"   ERROR: {e}")
            return

        # Step 3: Login
        print(f"\n3. Logging in...")
        try:
            response = await client.post(
                f"{BASE_URL}{API_PREFIX}/auth/login",
                json={
                    "email": TEST_EMAIL,
                    "password": TEST_PASSWORD
                }
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                token = data["data"]["access_token"]
                user_id = data["data"]["user_id"]
                school_id = data["data"]["school_id"]
                print(f"   ✅ Login successful")
                print(f"   User ID: {user_id}")
                print(f"   School ID: {school_id}")
                print(f"   Token: {token[:50]}...")
            else:
                print(f"   ❌ Login failed: {response.text}")
                return
        except Exception as e:
            print(f"   ERROR: {e}")
            return

        # Set auth header for subsequent requests
        headers = {"Authorization": f"Bearer {token}"}

        # Step 4: Test Topics Endpoint (504 Error)
        print(f"\n4. Testing Topics Endpoint (GET /api/v1/assessments/topics)...")
        print(f"   This is the endpoint that times out with 504...")

        try:
            response = await client.get(
                f"{BASE_URL}{API_PREFIX}/assessments/topics",
                headers=headers,
                timeout=60.0  # Wait up to 60 seconds
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Topics loaded successfully")
                print(f"   Response: {json.dumps(data, indent=2)}")
            elif response.status_code == 504:
                print(f"   ❌ 504 Gateway Timeout - Curriculum service is slow/down")
                print(f"   Response: {response.text}")
            elif response.status_code == 503:
                print(f"   ⚠️  503 Service Unavailable - Curriculum service not configured")
                print(f"   Response: {response.text}")
            else:
                print(f"   ❌ Error {response.status_code}: {response.text}")
        except httpx.TimeoutException:
            print(f"   ❌ CLIENT TIMEOUT - Request took longer than 60 seconds")
        except Exception as e:
            print(f"   ERROR: {e}")

        # Step 5: Check if audio conferencing endpoint exists
        print(f"\n5. Testing Audio Conferencing Endpoint Discovery...")
        print(f"   Checking OpenAPI spec for audio endpoints...")

        try:
            response = await client.get(f"{BASE_URL}{API_PREFIX}/openapi.json")
            if response.status_code == 200:
                spec = response.json()
                paths = spec.get("paths", {})

                # Look for audio-related endpoints
                audio_endpoints = [
                    path for path in paths.keys()
                    if "audio" in path.lower() or "token" in path.lower()
                ]

                if audio_endpoints:
                    print(f"   ✅ Found {len(audio_endpoints)} audio-related endpoints:")
                    for endpoint in audio_endpoints:
                        methods = list(paths[endpoint].keys())
                        print(f"      - {', '.join([m.upper() for m in methods])} {endpoint}")

                        # Show details of the audio token endpoint
                        if "/audio/token" in endpoint:
                            for method in methods:
                                summary = paths[endpoint][method].get("summary", "")
                                description = paths[endpoint][method].get("description", "")
                                print(f"        Summary: {summary}")
                                if description:
                                    print(f"        Description: {description[:200]}...")
                else:
                    print(f"   ❌ No audio-related endpoints found")
            else:
                print(f"   ❌ Failed to fetch OpenAPI spec: {response.status_code}")
        except Exception as e:
            print(f"   ERROR: {e}")

        # Step 6: List available arena endpoints
        print(f"\n6. Arena Endpoints Available:")
        if response.status_code == 200:
            arena_endpoints = [
                path for path in paths.keys()
                if "/arenas" in path
            ]
            print(f"   Found {len(arena_endpoints)} arena endpoints:")
            for endpoint in sorted(arena_endpoints):
                methods = list(paths[endpoint].keys())
                method_str = ", ".join([m.upper() for m in methods])
                summary = paths[endpoint][list(methods)[0]].get("summary", "")
                print(f"      {method_str:20} {endpoint}")
                if summary:
                    print(f"                           └─ {summary}")

        print("\n" + "=" * 60)
        print("TESTING COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_staging())
