from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from uuid import UUID

from app.models.enums import SchoolType, ProgramType, InquiryType

class ContactInquiryCreate(BaseModel):
    school_name: str = Field(..., min_length=1, description="School name cannot be empty")
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
    logo_url: Optional[str] = None

class SchoolProgramsUpdate(BaseModel):
    languages: List[str]


class SchoolProgramsResponse(BaseModel):
    """Response schema for school programs (languages) update."""

    languages: List[str]

class SchoolResponse(SchoolBase):
    id: UUID
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class LanguageResponse(BaseModel):
    id: int
    name: str
    code: str
    
    model_config = ConfigDict(from_attributes=True)
