"""Dependencies: X-School-Id header. DB session comes from database.get_db."""

from uuid import UUID
from fastapi import Header, HTTPException, status

__all__ = ["get_school_id"]


async def get_school_id(x_school_id: str = Header(..., alias="X-School-Id")) -> UUID:
    try:
        return UUID(x_school_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-School-Id header (must be a UUID)",
        )
