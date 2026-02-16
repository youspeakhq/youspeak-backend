from typing import Optional, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from app.models.enums import UserRole

class UserBase(BaseModel):
    email: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool = True

class StudentCreate(BaseModel):
    first_name: str
    last_name: str
    class_id: UUID
    lang_id: int
    # email is optional for students in some systems, but User model requires it.
    # We'll assume admin provides one or it's generated. Spec says CSV import.
    email: Optional[str] = None 
    password: Optional[str] = None # Admin might set default

class StudentUpdate(BaseModel):
    classroom_id: Optional[UUID] = None
    status: Optional[str] = None

class TeacherCreate(BaseModel):
    """Admin invites teacher. Teacher receives code via email and signs up with it."""
    first_name: str
    last_name: str
    email: str

class TeacherAssign(BaseModel):
    classroom_id: UUID

class UserResponse(UserBase):
    id: UUID
    school_id: UUID
    profile_picture_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class StudentCSVImport(BaseModel):
    # This might be used for validation of rows
    first_name: str
    last_name: str
    email: str
    class_name: Optional[str] = None
    language_code: Optional[str] = None
