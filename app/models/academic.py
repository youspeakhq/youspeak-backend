from datetime import datetime
from sqlalchemy import Column, String, Text, Date, Time, Boolean, Table, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.base import BaseModel, SchoolScopedMixin
from app.models.enums import DayOfWeek, ClassStatus, ProficiencyLevel, StudentRole



class Classroom(BaseModel, SchoolScopedMixin):
    """
    Admin-created organizational unit. Defines a learning track (language + level).
    Container for teachers and students. Semester-agnostic.
    """
    __tablename__ = "classrooms"

    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    level = Column(
        ENUM(ProficiencyLevel, name="proficiency_level", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
    )

    school = relationship("School", back_populates="classrooms")
    language = relationship("Language", back_populates="classrooms")
    teachers = relationship(
        "User",
        secondary="classroom_teachers",
        back_populates="taught_classrooms"
    )
    students = relationship(
        "User",
        secondary="classroom_students",
        back_populates="enrolled_classrooms"
    )
    classes = relationship("Class", back_populates="classroom", cascade="save-update, merge")

    def __repr__(self) -> str:
        return f"<Classroom {self.name}>"


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
    Class/Course section. Teacher-created scheduled offering.
    Represents a specific class taught in a semester. Optional link to Classroom.
    """
    __tablename__ = "classes"

    # Foreign Keys
    semester_id = Column(UUID(as_uuid=True), ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True)
    language_id = Column(ForeignKey("languages.id", ondelete="RESTRICT"), nullable=False, index=True)
    classroom_id = Column(UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Class Details
    name = Column(String(255), nullable=False)  # e.g., "French 101"
    sub_class = Column(String(100), nullable=True)  # Section: "Class A", "Morning Session"
    description = Column(Text, nullable=True)
    timeline = Column(String(100), nullable=True)  # e.g., "Jan 2026 - May 2026"
    status = Column(ENUM(ClassStatus, name="class_status"), default=ClassStatus.ACTIVE, nullable=False, index=True)
    
    # Relationships
    school = relationship("School", back_populates="classes")
    semester = relationship("Semester", back_populates="classes")
    language = relationship("Language", back_populates="classes")
    classroom = relationship("Classroom", back_populates="classes")
    
    schedules = relationship("ClassSchedule", back_populates="class_", cascade="all, delete-orphan")
    curriculums = relationship(
        "Curriculum", 
        secondary="curriculum_classes", 
        back_populates="classes"
    )
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
    day_of_week = Column(
        ENUM(DayOfWeek, name="day_of_week", values_callable=lambda x: [e.name for e in x]),
        nullable=False,
    )
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Relationships
    class_ = relationship("Class", back_populates="schedules")
    
    def __repr__(self) -> str:
        return f"<ClassSchedule {self.day_of_week} {self.start_time}-{self.end_time}>"


# Association table for Class <-> Student with role support (Pivot Table)
class_enrollments = Table(
    "class_enrollments",
    BaseModel.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role", ENUM(StudentRole, name="student_role"), default=StudentRole.STUDENT, nullable=False),
    Column("joined_at", DateTime, nullable=False)
)


# Association table for Classroom <-> Teacher
classroom_teachers = Table(
    "classroom_teachers",
    BaseModel.metadata,
    Column("classroom_id", UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Classroom <-> Student
classroom_students = Table(
    "classroom_students",
    BaseModel.metadata,
    Column("classroom_id", UUID(as_uuid=True), ForeignKey("classrooms.id", ondelete="CASCADE"), primary_key=True),
    Column("student_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Class <-> Teacher (Pivot Table)
teacher_assignments = Table(
    "teacher_assignments",
    BaseModel.metadata,
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
    Column("teacher_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("is_primary", Boolean, default=False, nullable=False)  # Main teacher flag
)

# Association table for Curriculum <-> Class (Pivot Table)
curriculum_classes = Table(
    "curriculum_classes",
    BaseModel.metadata,
    Column("curriculum_id", UUID(as_uuid=True), ForeignKey("curriculums.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True),
)
