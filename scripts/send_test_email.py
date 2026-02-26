#!/usr/bin/env python3
"""
Send a test teacher invite email. Use to verify Resend integration.

Usage:
  python scripts/send_test_email.py
  # Requires RESEND_API_KEY in .env (or export)

With an unverified domain, Resend only allows sending to the account email.
Default TO_EMAIL is set to that so the script works in development. Override with
  TEST_EMAIL=other@example.com python scripts/send_test_email.py
once you have verified a domain and set EMAIL_FROM to an address on it.
"""
import os
import sys

# Load .env from project root
try:
    from dotenv import load_dotenv
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(_root, ".env"))
except ImportError:
    pass

# Ensure we don't skip (development, not test)
if os.getenv("ENVIRONMENT", "development") == "test":
    os.environ["ENVIRONMENT"] = "development"

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.email_service import send_teacher_invite

# Resend allows only the account email when domain is unverified; override with TEST_EMAIL
TO_EMAIL = os.getenv("TEST_EMAIL", "youspeakhq@indiigoolabs.org")
FIRST_NAME = "Test"
ACCESS_CODE = "TEST-EMAIL-VERIFY"


def main():
    if not os.getenv("RESEND_API_KEY"):
        print("ERROR: RESEND_API_KEY must be set. Add to .env or export.")
        sys.exit(1)
    print(f"Sending test invite to {TO_EMAIL}...")
    ok = send_teacher_invite(TO_EMAIL, FIRST_NAME, ACCESS_CODE)
    if ok:
        print("SUCCESS: Email sent. Check inbox (and spam).")
    else:
        print("FAILED: Email was not sent. Check logs.")
        sys.exit(1)


if __name__ == "__main__":
    main()
