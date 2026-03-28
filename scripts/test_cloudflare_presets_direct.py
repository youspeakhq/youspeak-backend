#!/usr/bin/env python3
"""
Direct test of Cloudflare RealtimeKit API to verify preset name format.
Tests both hyphenated and underscore formats.
"""

import asyncio
import httpx
import os
import json


async def test_preset_format(account_id, app_id, api_token, meeting_id, preset_name):
    """
    Test adding a participant with a specific preset name format.

    Returns: (success: bool, response_text: str)
    """
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/realtime/kit/{app_id}/meetings/{meeting_id}/participants"

    payload = {
        "custom_participant_id": f"test_user_{preset_name.replace('-', '_').replace('_', '')}",
        "preset_name": preset_name,
        "name": f"Test User ({preset_name})"
    }

    print(f"\n{'='*70}")
    print(f"Testing preset: '{preset_name}'")
    print(f"{'='*70}")
    print(f"URL: {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            },
            timeout=10.0
        )

        print(f"\nStatus: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code in [200, 201]:
            print(f"✅ SUCCESS: Preset '{preset_name}' works!")
            return True, response.text
        else:
            print(f"❌ FAILED: Preset '{preset_name}' does not work")
            return False, response.text


async def create_test_meeting(account_id, app_id, api_token):
    """Create a test meeting for preset testing."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/realtime/kit/{app_id}/meetings"

    payload = {
        "title": "Preset Format Test Meeting",
        "record_on_start": False,
        "persist_chat": False
    }

    print(f"\nCreating test meeting...")
    print(f"URL: {url}")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            },
            timeout=10.0
        )

        if response.status_code in [200, 201]:
            data = response.json()
            # Try both "result" and "data" keys
            meeting_data = data.get("result") or data.get("data")
            meeting_id = meeting_data["id"]
            print(f"✅ Meeting created: {meeting_id}")
            return meeting_id
        else:
            print(f"❌ Failed to create meeting: {response.status_code}")
            print(f"Response: {response.text}")
            return None


async def main():
    """Run preset format tests."""
    print("="*70)
    print("CLOUDFLARE REALTIMEKIT PRESET FORMAT DIRECT TEST")
    print("="*70)

    # Get credentials from AWS Secrets Manager
    print("\n1. Fetching credentials from AWS Secrets Manager...")

    try:
        import boto3
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')

        # Fetch staging credentials
        account_id_secret = secrets_client.get_secret_value(SecretId='youspeak/cloudflare-account-id-staging')
        account_id = account_id_secret['SecretString']

        app_id_secret = secrets_client.get_secret_value(SecretId='youspeak/cloudflare-realtimekit-app-id-staging')
        app_id = app_id_secret['SecretString']

        api_token_secret = secrets_client.get_secret_value(SecretId='youspeak/cloudflare-api-token-staging')
        api_token = api_token_secret['SecretString']

        print(f"✅ Credentials retrieved")
        print(f"   Account ID: {account_id[:8]}...")
        print(f"   App ID: {app_id[:8]}...")
        print(f"   API Token: {api_token[:10]}...")

    except Exception as e:
        print(f"❌ Failed to fetch credentials: {e}")
        print("\nAlternatively, set environment variables:")
        print("  export CLOUDFLARE_ACCOUNT_ID=your_account_id")
        print("  export CLOUDFLARE_REALTIMEKIT_APP_ID=your_app_id")
        print("  export CLOUDFLARE_API_TOKEN=your_api_token")
        return

    # 2. Create a test meeting
    print("\n2. Creating test meeting...")
    meeting_id = await create_test_meeting(account_id, app_id, api_token)
    if not meeting_id:
        print("\n❌ Cannot proceed without a meeting")
        return

    # 3. Test different preset name formats
    print("\n3. Testing preset name formats...")

    preset_tests = [
        "group_call_host",        # Underscore (current code)
        "group-call-host",        # Hyphen (documentation)
        "group_call_participant", # Underscore (current code)
        "group-call-participant", # Hyphen (documentation)
        "webinar-host",           # Documentation example
        "webinar-participant",    # Documentation example
    ]

    results = {}
    for preset in preset_tests:
        success, response = await test_preset_format(
            account_id, app_id, api_token, meeting_id, preset
        )
        results[preset] = success
        await asyncio.sleep(0.5)  # Rate limiting

    # 4. Summary
    print("\n" + "="*70)
    print("RESULTS SUMMARY")
    print("="*70)

    working_presets = [name for name, success in results.items() if success]
    failed_presets = [name for name, success in results.items() if not success]

    if working_presets:
        print(f"\n✅ WORKING PRESETS:")
        for preset in working_presets:
            format_type = "UNDERSCORE" if "_" in preset else "HYPHEN"
            print(f"   - {preset} ({format_type})")

    if failed_presets:
        print(f"\n❌ FAILED PRESETS:")
        for preset in failed_presets:
            format_type = "UNDERSCORE" if "_" in preset else "HYPHEN"
            print(f"   - {preset} ({format_type})")

    # Analysis
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)

    underscore_works = any("_" in p for p in working_presets)
    hyphen_works = any("-" in p for p in working_presets)

    if underscore_works and not hyphen_works:
        print("\n✓ Cloudflare API accepts UNDERSCORE format (group_call_host)")
        print("  Current code is CORRECT ✓")
    elif hyphen_works and not underscore_works:
        print("\n✓ Cloudflare API accepts HYPHEN format (group-call-host)")
        print("  Current code needs UPDATE ⚠")
    elif underscore_works and hyphen_works:
        print("\n✓ Cloudflare API accepts BOTH formats")
        print("  Current code works, but hyphen is documented standard")
    else:
        print("\n⚠ Neither format worked - presets may not exist in app")
        print("  Check Cloudflare dashboard for available presets")

    print("\n" + "="*70)


if __name__ == "__main__":
    asyncio.run(main())
