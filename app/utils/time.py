"""Time Utilities for UTC management"""

from datetime import datetime, timezone

def get_utc_now() -> datetime:
    """
    Returns a naive UTC datetime. 
    Matches the existing DB schema (TIMESTAMP WITHOUT TIME ZONE).
    Avoids 'datetime.utcnow()' deprecation warnings.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
