"""Domain 3: Academic & Classroom Models"""

from sqlalchemy import Column, String, Text, Date, Time, Boolean, Table, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import DayOfWeek, ClassStatus, StudentRole


class Semester(BaseModel, SchoolScopedMixin):
    """
    Academic semester/term management.
    Defines the time period for classes.
    """
    __tablename__ = "semesters"
    
    name = Column(String(100), nullable=False)  # e.g., "Fall 2026"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Relationships
    school = relationship("School", back_populates="semesters")
    classes = relationship("Class", back_populates="semester", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Semester {self.name}>"


class Class(BaseModel, SchoolScopedMixin):
    """
    Class/Course section.
    Represents a specific class taught in a semester.
    """
    __tablename__ = "classes"
    
    # Foreign Keys
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # Class Details
    name = Column(String(255), nullable=False)  # e.g., "French 101"
    sub_class = Column(String(100), nullable=True)  # Section: "Class A", "Morning Session"
    description = Column(Text, nullable=True)
    status = Column(ENUM(ClassStatus, name="class_status"), default=ClassStatus.ACTIVE, nullable=False, index=True)
    
    # Relationships
    school = relationship("School", back_populates="classes")
    semester = relationship("Semester", back_populates="classes")
    language = relationship("Language", back_populates="classes")
    
    schedules = relationship("ClassSchedule", back_populates="class_", cascade="all, delete-orphan")
    curriculums = relationship("Curriculum", back_populates="class_", cascade="all, delete-orphan")
    learning_sessions = relationship("LearningSession", back_populates="class_", cascade="all, delete-orphan")
    arenas = relationship("Arena", back_populates="class_", cascade="all, delete-orphan")
    awards = relationship("Award", back_populates="class_", cascade="all, delete-orphan")
    announcements = relationship("Announcement", back_populates="class_")
    
    # Many-to-Many relationships
    teachers = relationship(
        "User",
        secondary="teacher_assignments",
        back_populates="taught_classes"
    )
    students = relationship(
        "User",
        secondary="class_enrollments",
        back_populates="enrolled_classes"
    )
    assignments = relationship(
        "Assignment",
        secondary="assignment_classes",
        back_populates="classes"
    )
    
    def __repr__(self) -> str:
        return f"<Class {self.name}>"


class ClassSchedule(BaseModel):
    """
    Weekly schedule for a class.
    Defines when a class meets during the week.
    """
    __tablename__ = "class_schedules"
    
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(ENUM(DayOfWeek, name="day_of_week"), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Relationships
    class_ = relationship("Class", back_populates="schedules")
    
    def __repr__(self) -> str:
        return f"<ClassSchedule {self.day_of_week} {self.start_time}-{self.end_time}>"


# Association table for Class <-> Student with role support (Pivot Table)
class ClassEnrollment(BaseModel):
    """
    Student enrollment in a class with role assignment.
    Supports special roles like Class Monitor, Time Keeper, etc.
    """
    __tablename__ = "class_enrollments"
    
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role = Column(ENUM(StudentRole, name="student_role"), default=StudentRole.STUDENT, nullable=False)
    joined_at = Column(DateTime, nullable=False)
    
    # Remove inherited id column since we're using composite PK
    __mapper_args__ = {
        "exclude_properties": ["id", "created_at", "updated_at"]
    }


# Association table for Class <-> Teacher (Pivot Table)
class TeacherAssignment(BaseModel):
    """
    Teacher assignment to a class.
    Supports primary teacher designation.
    """
    __tablename__ = "teacher_assignments"
    
    class_id = Column(UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    is_primary = Column(Boolean, default=False, nullable=False)  # Main teacher flag
    
    # Remove inherited id column since we're using composite PK
    __mapper_args__ = {
        "exclude_properties": ["id", "created_at", "updated_at"]
    }
