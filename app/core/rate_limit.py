"""Rate limiting configuration"""

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

# Initialize default rate limiter (IP-based)
limiter = Limiter(key_func=get_remote_address)


# User-aware key function for authenticated endpoints
def get_user_key_with_role(request: Request) -> str:
    """
    Extract user ID and role from JWT for user-based rate limiting.
    Falls back to IP address if no valid token is present.

    Returns: "user_id:role" for authenticated users, or IP address for unauthenticated.
    """
    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return get_remote_address(request)

        token = auth_header.replace("Bearer ", "")

        # Decode JWT to get user info
        from app.core.security import decode_token
        payload = decode_token(token)

        if not payload:
            return get_remote_address(request)

        user_id = payload.get("sub", "")
        role = payload.get("role", "")

        if user_id and role:
            return f"{user_id}:{role}"

        return get_remote_address(request)

    except Exception:
        # Fallback to IP on any error
        return get_remote_address(request)


# Initialize user-aware limiter for authenticated endpoints
user_limiter = Limiter(key_func=get_user_key_with_role)
