from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
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
    class_id: Optional[UUID] = None
    lang_id: int
    email: Optional[str] = None
    password: Optional[str] = None
    student_id: Optional[str] = None  # Human-readable ID (e.g. 2025-001). Auto-generated if omitted.

class StudentUpdate(BaseModel):
    classroom_id: Optional[UUID] = None
    status: Optional[str] = None

class TeacherCreate(BaseModel):
    """Admin creates teacher (is_active=False). Teacher activates via code at register."""
    first_name: str
    last_name: str
    email: str
    classroom_ids: Optional[List[UUID]] = None

class TeacherAssign(BaseModel):
    classroom_id: UUID

class UserResponse(UserBase):
    id: UUID
    school_id: UUID
    profile_picture_url: Optional[str] = None
    student_number: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentCSVImport(BaseModel):
    # This might be used for validation of rows
    first_name: str
    last_name: str
    email: str
    class_name: Optional[str] = None
    language_code: Optional[str] = None
