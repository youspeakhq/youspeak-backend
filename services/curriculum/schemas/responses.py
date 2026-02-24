"""Response envelopes for curriculum API."""

from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: str = "Operation successful"


class PaginatedResponse(BaseModel, Generic[T]):
    data: List[T]
    meta: Dict[str, Any]
