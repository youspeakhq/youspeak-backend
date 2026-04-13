"""
One-time script to enable transcription on Cloudflare RealtimeKit presets.

Both group_call_host and group_call_participant presets need
transcription_enabled=true for live transcription to work.

Usage:
    python scripts/enable_transcription_presets.py

Requires environment variables (or AWS Secrets Manager):
    - CLOUDFLARE_ACCOUNT_ID
    - CLOUDFLARE_REALTIMEKIT_APP_ID
    - CLOUDFLARE_API_TOKEN
"""

import asyncio
import os
import sys
import httpx

# Preset IDs for the YouSpeak staging app
PRESETS = {
    "group_call_host": "873ba0af-4098-468e-9390-efc66e5e3e56",
    "group_call_participant": "e140b8e2-1c1c-401e-8633-35d0d92ac806",
}


async def enable_transcription():
    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    app_id = os.environ.get("CLOUDFLARE_REALTIMEKIT_APP_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

    if not all([account_id, app_id, api_token]):
        print("ERROR: Missing environment variables. Set CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_REALTIMEKIT_APP_ID, CLOUDFLARE_API_TOKEN")
        sys.exit(1)

    base_url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/realtime/kit/{app_id}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        for name, preset_id in PRESETS.items():
            print(f"\nUpdating preset '{name}' ({preset_id})...")

            response = await client.patch(
                f"{base_url}/presets/{preset_id}",
                json={"permissions": {"transcription_enabled": True}},
                headers=headers,
                timeout=10.0
            )

            if response.status_code in (200, 201):
                print(f"  OK - transcription_enabled set to true")
                print(f"  Response: {response.json()}")
            else:
                print(f"  FAILED - HTTP {response.status_code}")
                print(f"  Response: {response.text}")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(enable_transcription())
