from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
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
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
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
    languages: List[str] = Field(default_factory=list, description="Language codes offered by the school")

    @field_validator("languages", mode="before")
    @classmethod
    def languages_to_codes(cls, v: Any) -> List[str]:
        if not v:
            return []
        return [x.code if hasattr(x, "code") else x for x in v]

    model_config = ConfigDict(from_attributes=True)


class LanguageCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Language name (e.g., 'German', 'Mandarin')")
    code: str = Field(..., pattern=r"^[a-z]{2}$", description="ISO 639-1 two-letter lowercase code (e.g., 'de', 'zh')")


class LanguageResponse(BaseModel):
    id: int
    name: str
    code: str

    model_config = ConfigDict(from_attributes=True)
