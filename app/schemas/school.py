from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from uuid import UUID

from app.models.enums import SchoolType, ProgramType, InquiryType

class ContactInquiryCreate(BaseModel):
    school_name: str
    email: EmailStr
    inquiry_type: InquiryType
    message: str

class SchoolBase(BaseModel):
    name: str
    school_type: SchoolType
    program_type: ProgramType
    address_country: Optional[str] = None
    address_state: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    logo_url: Optional[str] = None

class SchoolCreate(SchoolBase):
    pass

class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    address_country: Optional[str] = None
    address_state: Optional[str] = None
    address_city: Optional[str] = None
    address_zip: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None

class SchoolProgramsUpdate(BaseModel):
    program_id: Optional[str] = None # Assuming referencing an ID or enum
    languages: List[str]

class SchoolResponse(SchoolBase):
    id: UUID
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class LanguageResponse(BaseModel):
    id: int
    name: str
    code: str
    
    class Config:
        from_attributes = True
