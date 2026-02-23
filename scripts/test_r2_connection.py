#!/usr/bin/env python3
"""
Test Cloudflare R2 connectivity and public URL.
Uses R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME from env (or .env).
Run from repo root: python scripts/test_r2_connection.py
Or after exporting vars from Terraform secrets: ./scripts/check_r2_credentials_terraform.sh
"""
import sys
from pathlib import Path

# Ensure app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings


def main() -> None:
    import boto3
    from botocore.exceptions import ClientError
    from botocore.config import Config as BotocoreConfig

    # Strip first so values from Secrets Manager (possible newlines/whitespace) don't cause SignatureDoesNotMatch.
    # Validate after strip: whitespace-only credentials become empty and would produce invalid endpoint/auth.
    account_id = (settings.R2_ACCOUNT_ID or "").strip()
    access_key = (settings.R2_ACCESS_KEY_ID or "").strip()
    secret_key = (settings.R2_SECRET_ACCESS_KEY or "").strip()
    bucket = (settings.R2_BUCKET_NAME or "").strip() or "youspeak"

    if not account_id or not access_key or not secret_key:
        print("Missing R2 credentials. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY (env or .env)")
        sys.exit(1)

    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    config_kwargs = {
        "signature_version": "s3v4",
        "s3": {"addressing_style": "path"},
    }
    try:
        config = BotocoreConfig(
            **config_kwargs,
            request_checksum_calculation="WHEN_REQUIRED",
            response_checksum_validation="WHEN_REQUIRED",
        )
    except TypeError:
        config = BotocoreConfig(**config_kwargs)
    client = boto3.client(
        service_name="s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=config,
    )

    # 1) Bucket access
    try:
        client.head_bucket(Bucket=bucket)
        print(f"OK Bucket '{bucket}' exists and is accessible")
    except ClientError as e:
        print(f"FAIL head_bucket: {e}")
        sys.exit(1)

    # 2) Upload test object
    test_key = "_test/connection-check.txt"
    body = b"R2 connection test from youspeak-backend"
    try:
        client.put_object(
            Bucket=bucket,
            Key=test_key,
            Body=body,
            ContentType="text/plain",
        )
        print(f"OK Uploaded test object: {test_key}")
    except ClientError as e:
        print(f"FAIL put_object: {e}")
        sys.exit(1)

    # 3) Public URL (dev URL or custom domain)
    base = settings.STORAGE_PUBLIC_BASE_URL.rstrip("/")
    public_url = f"{base}/{test_key}"
    print(f"   Public URL: {public_url}")

    # 4) Verify public read (optional – dev URL may be rate-limited)
    try:
        import urllib.request
        with urllib.request.urlopen(public_url, timeout=10) as resp:
            data = resp.read()
            if data == body:
                print("OK Public URL returns the test object")
            else:
                print("WARN Public URL returned different content (may be custom domain or caching)")
    except Exception as e:
        print(f"WARN Could not fetch public URL (rate limit or domain not set): {e}")

    print("R2 connection test passed.")
    # Optionally delete test object
    try:
        client.delete_object(Bucket=bucket, Key=test_key)
        print("   Test object deleted.")
    except ClientError:
        pass


if __name__ == "__main__":
    main()
