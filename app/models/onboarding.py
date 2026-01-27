"""Domain 1: Global & Onboarding Models"""

from sqlalchemy import Column, String, Text, Table, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, StatusMixin
from app.models.enums import InquiryType, SchoolType, ProgramType


class ContactInquiry(BaseModel):
    """
    Pre-onboarding contact inquiries.
    Used for demo requests, billing questions, etc.
    """
    __tablename__ = "contact_inquiries"
    
    school_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    inquiry_type = Column(ENUM(InquiryType, name="inquiry_type"), nullable=False)
    message = Column(Text, nullable=False)
    
    def __repr__(self) -> str:
        return f"<ContactInquiry {self.school_name} - {self.inquiry_type}>"


class School(BaseModel, StatusMixin):
    """
    Tenant/School model - the multi-tenant anchor.
    Each school is a separate organization using the platform.
    """
    __tablename__ = "schools"
    
    # Basic Information
    name = Column(String(255), nullable=False)
    school_type = Column(ENUM(SchoolType, name="school_type"), nullable=False)
    program_type = Column(ENUM(ProgramType, name="program_type"), nullable=False)
    
    # Address
    address_country = Column(String(100), nullable=True)
    address_state = Column(String(100), nullable=True)
    address_city = Column(String(100), nullable=True)
    address_zip = Column(String(20), nullable=True)
    
    # Branding
    logo_url = Column(Text, nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    semesters = relationship("Semester", back_populates="school", cascade="all, delete-orphan")
    classes = relationship("Class", back_populates="school", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="school", cascade="all, delete-orphan")
    bills = relationship("Bill", back_populates="school", cascade="all, delete-orphan")
    
    # Many-to-Many: Languages offered by school
    languages = relationship(
        "Language",
        secondary="school_languages",
        back_populates="schools"
    )
    
    def __repr__(self) -> str:
        return f"<School {self.name}>"


class Language(BaseModel):
    """
    Global language reference table.
    Contains all languages available on the platform.
    """
    __tablename__ = "languages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)  # e.g., "French", "Spanish"
    code = Column(String(10), nullable=False, unique=True)   # e.g., "fr", "es"
    
    # Relationships
    schools = relationship(
        "School",
        secondary="school_languages",
        back_populates="languages"
    )
    classes = relationship("Class", back_populates="language")
    curriculums = relationship("Curriculum", back_populates="language")
    
    def __repr__(self) -> str:
        return f"<Language {self.name} ({self.code})>"


# Association table for School <-> Language (Many-to-Many)
school_languages = Table(
    "school_languages",
    BaseModel.metadata,
    Column("school_id", UUID(as_uuid=True), ForeignKey("schools.id", ondelete="CASCADE"), primary_key=True),
    Column("language_id", Integer, ForeignKey("languages.id", ondelete="CASCADE"), primary_key=True)
)
