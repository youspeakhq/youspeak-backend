"""Security Utilities for Arena Service"""

from typing import Optional
from jose import JWTError, jwt
from .config import settings


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token using shared secret."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def get_user_id_from_token(token: str) -> Optional[str]:
    """Extract user_id (sub) from token."""
    payload = decode_token(token)
    if payload:
        return payload.get("sub")
    return None
