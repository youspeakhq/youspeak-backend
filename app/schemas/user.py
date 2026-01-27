"""User Pydantic Schemas"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict


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
    is_active: bool
    is_superuser: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


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


# Pagination Schema
class PaginatedUsers(BaseModel):
    """Schema for paginated user list"""
    items: list[User]
    total: int
    page: int
    page_size: int
    total_pages: int
