"""Security and Authentication Utilities"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings

# Bcrypt limit; longer passwords must be truncated
_BCRYPT_MAX_BYTES = 72


def _truncate_password_for_bcrypt(password: str) -> bytes:
    """Truncate password to bcrypt's 72-byte limit, respecting UTF-8 boundaries."""
    encoded = password.encode("utf-8")
    if len(encoded) <= _BCRYPT_MAX_BYTES:
        return encoded
    truncated = encoded[:_BCRYPT_MAX_BYTES]
    while truncated:
        try:
            truncated.decode("utf-8")
            return truncated
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return b""


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    Bcrypt has a 72-byte limit; longer passwords are truncated to avoid ValueError.
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password (ASCII string for DB storage)
    """
    pwd_bytes = _truncate_password_for_bcrypt(password)
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("ascii")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    pwd_bytes = _truncate_password_for_bcrypt(plain_password)
    hash_bytes = hashed_password.encode("ascii") if isinstance(hashed_password, str) else hashed_password
    return bcrypt.checkpw(pwd_bytes, hash_bytes)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in the token (usually {"sub": user_id})
        expires_delta: Optional custom expiration time
        
    Returns:
        Encoded JWT token
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create a JWT refresh token.
    
    Args:
        data: Data to encode in the token (usually {"sub": user_id})
        
    Returns:
        Encoded JWT refresh token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token to decode
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_access_code(length: int = 8) -> str:
    """
    Generate a random access code for teacher invitations.
    
    Args:
        length: Length of the code (default: 8)
        
    Returns:
        Random alphanumeric code (uppercase)
    """
    # Use uppercase letters and digits, excluding similar-looking characters
    alphabet = string.ascii_uppercase + string.digits
    alphabet = alphabet.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    code = ''.join(secrets.choice(alphabet) for _ in range(length))
    return code


def generate_password_reset_token(user_id: str) -> str:
    """
    Generate a password reset token.
    
    Args:
        user_id: User ID
        
    Returns:
        JWT token for password reset (expires in 1 hour)
    """
    data = {"sub": user_id, "purpose": "password_reset"}
    expire = datetime.utcnow() + timedelta(hours=1)
    
    to_encode = data.copy()
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_password_reset_token(token: str) -> Optional[str]:
    """
    Verify a password reset token and extract user_id.
    
    Args:
        token: Password reset token
        
    Returns:
        user_id if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("purpose") != "password_reset":
            return None
        return payload.get("sub")
    except JWTError:
        return None
