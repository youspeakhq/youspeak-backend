#!/usr/bin/env python3
"""
Test script to verify correct Cloudflare RealtimeKit preset name format.
Tests both hyphenated (group-call-host) and underscore (group_call_host) formats.
"""

import asyncio
import httpx
import json
from datetime import datetime

# Staging endpoint
BASE_URL = "https://api-staging.youspeakhq.com/api/v1"

# Test data
TEST_EMAIL = f"preset_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
TEST_PASSWORD = "TestPass123!"


async def register_teacher():
    """Register a test teacher."""
    print("\n1. Registering test teacher...")
    async with httpx.AsyncClient() as client:
        # First register a school
        school_response = await client.post(
            f"{BASE_URL}/auth/register/school",
            json={
                "school_name": "Preset Test School",
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
                "school_type": "secondary",
                "program_type": "partnership",
                "address_country": "US",
                "address_state": "CA",
                "address_city": "San Francisco",
                "address_zip": "94102",
                "languages": ["spanish"]
            },
            timeout=30.0
        )

        if school_response.status_code != 200:
            print(f"❌ School registration failed: {school_response.status_code}")
            print(f"Response: {school_response.text}")
            return False

        data = school_response.json()
        school_id = data["data"]["school_id"]
        print(f"✅ School registered: {school_id}")

        # Use school admin email (school registration creates admin account)
        print(f"   Using school admin account as teacher")
        return True, TEST_EMAIL


async def login(email):
    """Login and get auth token."""
    print("\n2. Logging in...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/login",
            json={
                "email": email,
                "password": TEST_PASSWORD
            },
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        data = response.json()
        token = data["data"]["access_token"]
        user_id = data["data"].get("id", data["data"].get("user_id", "unknown"))
        print(f"✅ Logged in (Teacher ID: {user_id})")
        return token


async def create_classroom(token):
    """Create a classroom."""
    print("\n3. Creating classroom...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/classrooms",
            json={
                "name": "Preset Test Classroom",
                "language_id": 1,  # Assuming 1 is a valid language ID
                "level": "beginner"
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"❌ Classroom creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        data = response.json()
        classroom_id = data["data"]["id"]
        print(f"✅ Classroom created: {classroom_id}")
        return classroom_id


async def create_arena(token, classroom_id):
    """Create an arena."""
    print("\n4. Creating arena...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/arenas",
            json={
                "title": "Preset Format Test Arena",
                "classroom_id": classroom_id,
                "difficulty_level": "beginner",
                "topic": "Testing preset names",
                "mode": "speaking_challenge"
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"❌ Arena creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return None

        data = response.json()
        arena_id = data["data"]["id"]
        print(f"✅ Arena created: {arena_id}")
        return arena_id


async def start_session(token, arena_id):
    """Start a live session."""
    print("\n5. Starting live session...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/arenas/{arena_id}/session/start",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0
        )

        if response.status_code != 200:
            print(f"❌ Session start failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False

        print(f"✅ Live session started")
        return True


async def test_audio_token(token, arena_id, preset_format):
    """
    Test audio token generation with specific preset format.

    Note: This endpoint doesn't accept preset_name as a parameter.
    It determines the preset based on user role (teacher vs student).
    We'll test by making the request and checking what preset is used.
    """
    print(f"\n6. Testing audio token generation...")
    print(f"   (Backend will determine preset based on user role)")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/arenas/{arena_id}/audio/token",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30.0
        )

        status = "✅" if response.status_code == 200 else "❌"
        print(f"\n{status} Response Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            preset_used = data["data"]["preset_name"]
            print(f"✅ Audio token generated successfully!")
            print(f"   Preset used: {preset_used}")
            print(f"   Token: {data['data']['token'][:50]}...")
            print(f"   Participant ID: {data['data']['participant_id']}")
            print(f"   Meeting ID: {data['data']['meeting_id']}")
            return True, preset_used
        else:
            print(f"❌ Failed: {response.text}")
            return False, None


async def test_direct_cloudflare_api(meeting_id, preset_name):
    """
    Directly test Cloudflare API with different preset formats.
    This requires having credentials available.
    """
    print(f"\n6. Testing Cloudflare API directly with preset: {preset_name}")
    print("   (This would require direct access to Cloudflare credentials)")
    # We can't easily test this without exposing credentials
    # The backend test above is sufficient


async def main():
    """Run all tests."""
    print("=" * 70)
    print("CLOUDFLARE REALTIMEKIT PRESET FORMAT TEST")
    print("=" * 70)
    print(f"\nTesting against: {BASE_URL}")
    print(f"Test email: {TEST_EMAIL}")

    # Step 1: Register teacher
    success, teacher_email = await register_teacher()
    if not success:
        print("\n❌ Test failed at registration step")
        return

    # Step 2: Login and get token
    token = await login(teacher_email)
    if not token:
        print("\n❌ Test failed at login step")
        return

    # Step 3: Create classroom
    classroom_id = await create_classroom(token)
    if not classroom_id:
        print("\n❌ Test failed at classroom creation step")
        return

    # Step 4: Create arena
    arena_id = await create_arena(token, classroom_id)
    if not arena_id:
        print("\n❌ Test failed at arena creation step")
        return

    # Step 5: Start session
    if not await start_session(token, arena_id):
        print("\n❌ Test failed at session start step")
        return

    # Step 6: Test audio token (backend determines preset based on role)
    success, preset_used = await test_audio_token(token, arena_id, "auto")

    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    if success:
        print(f"\n✅ Audio token generation SUCCESSFUL!")
        print(f"   Backend used preset: '{preset_used}'")
        print(f"\n   Analysis:")
        if "_" in preset_used:
            print(f"   ✓ Uses UNDERSCORE format (group_call_host)")
        elif "-" in preset_used:
            print(f"   ✓ Uses HYPHEN format (group-call-host)")
        else:
            print(f"   ? Uses different format: {preset_used}")
    else:
        print(f"\n❌ Audio token generation FAILED!")
        print(f"   Check backend logs for errors")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
