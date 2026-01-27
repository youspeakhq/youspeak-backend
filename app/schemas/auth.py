from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

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
    account_type: str = "school"
    email: EmailStr
    password: str
    school_name: str
    # Admin details
    admin_first_name: str
    admin_last_name: str

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
