"""Enhanced API Dependencies with RBAC"""

from typing import Optional
from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database import get_db
from app.core.security import decode_token
from app.services.user_service import UserService
from app.models.user import User
from app.models.enums import UserRole

# Security scheme for bearer token (auto_error=False so we can return 401 for missing auth)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        db: Database session
        credentials: HTTP authorization credentials

    Returns:
        Current user

    Raises:
        HTTPException: If token is missing, invalid or user not found
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials

    # Decode token
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user ID from token
    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )

    # Check for soft delete
    if user.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account has been deleted"
        )

    return user


async def require_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be a school admin.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user (if admin)

    Raises:
        HTTPException: If user is not an admin
    """
    if current_user.role != UserRole.SCHOOL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_teacher(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be a teacher.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user (if teacher)

    Raises:
        HTTPException: If user is not a teacher
    """
    if current_user.role != UserRole.TEACHER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher access required"
        )
    return current_user


async def require_teacher_or_admin(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be a teacher or admin.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user (if teacher or admin)

    Raises:
        HTTPException: If user is neither teacher nor admin
    """
    if current_user.role not in [UserRole.TEACHER, UserRole.SCHOOL_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher or Admin access required"
        )
    return current_user


async def require_student(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Require user to be a student.

    Args:
        current_user: Current authenticated user

    Returns:
        Current user (if student)

    Raises:
        HTTPException: If user is not a student
    """
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student access required"
        )
    return current_user


async def authenticate_websocket(
    websocket: WebSocket,
    db: AsyncSession
) -> Optional[User]:
    """
    Authenticate WebSocket connection using token from query params or headers.

    Args:
        websocket: WebSocket connection
        db: Database session

    Returns:
        Authenticated user or None if authentication fails

    Note:
        Closes WebSocket with code 4001 (Unauthorized) if authentication fails.
    """
    # Try to get token from query params first (common for WebSocket clients)
    token = websocket.query_params.get("token")

    # Fallback to Authorization header
    if not token:
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return None

    # Decode token
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=4001, reason="Invalid authentication token")
        return None

    # Get user ID
    user_id_str = payload.get("sub")
    if not user_id_str:
        await websocket.close(code=4001, reason="Invalid token payload")
        return None

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        await websocket.close(code=4001, reason="Invalid user ID format")
        return None

    # Get user from database
    user = await UserService.get_user_by_id(db, user_id)
    if not user or not user.is_active:
        await websocket.close(code=4001, reason="User not found or inactive")
        return None

    return user
