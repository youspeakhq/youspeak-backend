"""User Pydantic Schemas"""

from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, model_validator

from app.models.enums import UserRole
from app.schemas.academic import ClassroomBrief
from app.schemas.student import LanguageBrief


# Base User Schema


class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr
    full_name: Optional[str] = None


# User Registration Schema


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


# User Update Schema


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)


# User Response Schema


class User(UserBase):
    """Schema for user responses"""
    id: UUID
    email: EmailStr
    is_active: bool
    is_superuser: bool = False  # Deprecated but kept for compat
    role: UserRole
    school_id: Optional[UUID] = None
    profile_picture_url: Optional[str] = None
    student_number: Optional[str] = None
    language_id: Optional[int] = None
    language: Optional[LanguageBrief] = None
    is_verified: bool = False
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    classrooms: List[ClassroomBrief] = []

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def orm_safe_language(cls, v: Any) -> Any:
        """When building from an ORM User, do not access the language relationship
        (avoids MissingGreenlet from lazy load). Use language_id only; callers that
        need nested language should pass it explicitly after eager load.
        """
        if hasattr(v, "__tablename__") and getattr(v, "__tablename__", None) == "users":
            return {
                "id": v.id,
                "email": v.email,
                "full_name": getattr(v, "full_name", None)
                or (f"{getattr(v, 'first_name', '')} {getattr(v, 'last_name', '')}".strip() or None),
                "is_active": v.is_active,
                "is_superuser": getattr(v, "is_superuser", False),
                "role": v.role,
                "school_id": getattr(v, "school_id", None),
                "profile_picture_url": getattr(v, "profile_picture_url", None),
                "student_number": getattr(v, "student_number", None),
                "language_id": getattr(v, "language_id", None),
                "language": None,
                "is_verified": getattr(v, "is_verified", False),
                "created_at": v.created_at,
                "updated_at": v.updated_at,
                "last_login": getattr(v, "last_login", None),
                "classrooms": [],
            }
        return v


UserResponse = User


# User Login Schema


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str


# Token Schemas


class Token(BaseModel):
    """Schema for authentication tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Schema for token payload data"""
    user_id: Optional[UUID] = None


# Password Change Schema


class PasswordChange(BaseModel):
    """Schema for changing password"""
    current_password: str
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters")


class DeleteAccountRequest(BaseModel):
    """Schema for self-service account deletion (password confirmation)."""
    password: str = Field(..., description="Current password to confirm deletion")
