"""
Cloudflare R2 (S3-compatible) storage. Uses global config; no per-call reconfiguration.
"""
import asyncio
from io import BytesIO
from typing import Optional
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _r2_client():
    if not settings.R2_ACCOUNT_ID or not settings.R2_ACCESS_KEY_ID or not settings.R2_SECRET_ACCESS_KEY:
        raise RuntimeError(
            "R2 storage not configured: set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY"
        )
    return boto3.client(
        service_name="s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=boto3.session.Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def public_url(key: str) -> str:
    """Build public URL for an object key (custom domain or R2 dev URL)."""
    base = settings.STORAGE_PUBLIC_BASE_URL.rstrip("/")
    key = key.lstrip("/")
    return f"{base}/{key}" if key else base


async def upload(
    key_prefix: str,
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
    *,
    unique: bool = True,
) -> str:
    """
    Upload bytes to R2 and return the public URL.
    key_prefix: e.g. "curriculums/{school_id}" or "logos/{school_id}"
    filename: original filename (used for extension; if unique=True, a UUID is prepended).
    """
    if unique:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        object_name = f"{key_prefix}/{uuid4().hex}.{ext}" if ext else f"{key_prefix}/{uuid4().hex}"
    else:
        object_name = f"{key_prefix}/{filename}"

    client = _r2_client()
    bucket = settings.R2_BUCKET_NAME
    extra = {"ContentType": content_type} if content_type else {}

    def _put():
        try:
            client.upload_fileobj(
                BytesIO(content),
                bucket,
                object_name,
                ExtraArgs=extra,
            )
        except ClientError as e:
            raise RuntimeError(f"Storage upload failed: {e}") from e

    await asyncio.to_thread(_put)
    return public_url(object_name)
