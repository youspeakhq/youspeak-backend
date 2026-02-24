"""Time utilities. Returns naive UTC to match TIMESTAMP WITHOUT TIME ZONE."""

from datetime import datetime, timezone


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
