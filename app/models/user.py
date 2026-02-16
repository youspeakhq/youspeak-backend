"""Domain 2: User & Authentication Model"""

from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin, SoftDeleteMixin
from app.models.enums import UserRole


class User(BaseModel, SchoolScopedMixin, SoftDeleteMixin):
    """
    Unified user model for all roles (School Admin, Teacher, Student).
    Implements multi-tenancy via school_id and soft delete for data preservation.
    """
    __tablename__ = "users"
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    # Personal Information
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    profile_picture_url = Column(String(500), nullable=True)
    student_number = Column(String(20), nullable=True)
    
    # Role & Permissions (RBAC)
    role = Column(ENUM(UserRole, name="user_role"), nullable=False, index=True)
    
    # Security
    is_2fa_enabled = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    school = relationship("School", back_populates="users")
    
    # Teacher relationships
    taught_classes = relationship(
        "Class",
        secondary="teacher_assignments",
        back_populates="teachers"
    )
    taught_classrooms = relationship(
        "Classroom",
        secondary="classroom_teachers",
        back_populates="teachers"
    )
    created_questions = relationship("Question", back_populates="teacher")
    created_assignments = relationship("Assignment", back_populates="teacher")
    
    # Student relationships
    enrolled_classes = relationship(
        "Class",
        secondary="class_enrollments",
        back_populates="students"
    )
    enrolled_classrooms = relationship(
        "Classroom",
        secondary="classroom_students",
        back_populates="students"
    )
    submissions = relationship("StudentSubmission", back_populates="student")
    arena_performances = relationship("ArenaPerformer", back_populates="user")
    awards = relationship("Award", back_populates="student")
    
    # Communication
    authored_announcements = relationship("Announcement", back_populates="author")
    started_sessions = relationship("LearningSession", back_populates="started_by_user")
    
    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_admin(self) -> bool:
        """Check if user is school admin"""
        return self.role == UserRole.SCHOOL_ADMIN
    
    @property
    def is_teacher(self) -> bool:
        """Check if user is teacher"""
        return self.role == UserRole.TEACHER
    
    @property
    def is_student(self) -> bool:
        """Check if user is student"""
        return self.role == UserRole.STUDENT
    
    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

