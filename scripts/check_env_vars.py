#!/usr/bin/env python3
"""Quick check to see if Cloudflare env vars are loaded."""
import os

print("Checking Cloudflare environment variables:")
print(f"CLOUDFLARE_ACCOUNT_ID: {'✓ SET' if os.getenv('CLOUDFLARE_ACCOUNT_ID') else '✗ NOT SET'}")
print(f"CLOUDFLARE_REALTIMEKIT_APP_ID: {'✓ SET' if os.getenv('CLOUDFLARE_REALTIMEKIT_APP_ID') else '✗ NOT SET'}")
print(f"CLOUDFLARE_API_TOKEN: {'✓ SET' if os.getenv('CLOUDFLARE_API_TOKEN') else '✗ NOT SET'}")
