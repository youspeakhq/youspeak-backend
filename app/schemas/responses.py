"""Standardized API Response Schemas"""

from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field, ConfigDict


T = TypeVar('T')


class SuccessResponse(BaseModel, Generic[T]):
    """
    Standard success response envelope.
    
    Example:
        {
            "success": true,
            "data": {...},
            "message": "Operation successful"
        }
    """
    success: bool = True
    data: T
    message: str = "Operation successful"


class ErrorDetail(BaseModel):
    """Error details structure"""
    code: str
    message: str


class ErrorResponse(BaseModel):
    """
    Standard error response envelope.
    
    Example:
        {
            "success": false,
            "error": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "The student with ID 123 does not exist."
            }
        }
    """
    success: bool = False
    error: ErrorDetail


class PaginationMeta(BaseModel):
    """Pagination metadata"""
    page: int = Field(..., ge=1, description="Current page number")
    page_size: int = Field(..., ge=1, le=100, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Paginated response with metadata.
    
    Example:
        {
            "success": true,
            "data": [...],
            "meta": {
                "page": 1,
                "page_size": 10,
                "total": 50,
                "total_pages": 5
            },
            "message": "Operation successful"
        }
    """
    success: bool = True
    data: list[T]
    meta: PaginationMeta
    message: str = "Operation successful"
