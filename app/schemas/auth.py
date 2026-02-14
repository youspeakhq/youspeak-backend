from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

from app.models.enums import SchoolType, ProgramType

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    school_id: Optional[str] = None

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None

class RegisterSchoolRequest(BaseModel):
    """School onboarding - aligns with frontend screens (login, profile, enrollment)."""
    account_type: str = "school"
    email: EmailStr
    password: str
    school_name: str = Field(..., min_length=1, description="School name cannot be empty")
    school_type: Optional[SchoolType] = None
    program_type: Optional[ProgramType] = None
    address_country: Optional[str] = None
    address_state: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    languages: Optional[List[str]] = None

class RegisterTeacherRequest(BaseModel):
    access_code: str
    first_name: str
    last_name: str
    email: EmailStr
    password: str

class VerifyCodeRequest(BaseModel):
    access_code: str

class PasswordResetRequest(BaseModel):
    token: str
    new_password: str

class PasswordResetEmailRequest(BaseModel):
    email: EmailStr
