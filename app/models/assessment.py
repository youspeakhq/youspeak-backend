"""Domain 5: Assessment Models (Question Bank, Assignments, Submissions)"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Numeric, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship

from app.models.base import BaseModel
from app.models.enums import QuestionType, AssignmentType, AssignmentStatus, SubmissionStatus


class Question(BaseModel):
    """
    Question bank for assessments.
    Teachers create and reuse questions across multiple assignments.
    """
    __tablename__ = "questions"
    
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    correct_answer = Column(Text, nullable=True)  # TEXT or JSON for multiple choice
    type = Column(ENUM(QuestionType, name="question_type"), nullable=False)
    
    # Relationships
    teacher = relationship("User", back_populates="created_questions")
    assignments = relationship(
        "Assignment",
        secondary="assignment_questions",
        back_populates="questions"
    )
    
    def __repr__(self) -> str:
        return f"<Question {self.type}>"


class Assignment(BaseModel):
    """
    Assignment/assessment task definition.
    Can be distributed to multiple classes.
    """
    __tablename__ = "assignments"
    
    teacher_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    instructions = Column(Text, nullable=True)
    type = Column(ENUM(AssignmentType, name="assignment_type"), nullable=False)
    due_date = Column(DateTime, nullable=True)
    status = Column(ENUM(AssignmentStatus, name="assignment_status"), default=AssignmentStatus.DRAFT, nullable=False, index=True)
    
    # Relationships
    teacher = relationship("User", back_populates="created_assignments")
    classes = relationship(
        "Class",
        secondary="assignment_classes",
        back_populates="assignments"
    )
    questions = relationship(
        "Question",
        secondary="assignment_questions",
        back_populates="assignments"
    )
    submissions = relationship("StudentSubmission", back_populates="assignment", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Assignment {self.title}>"


# Association table for Assignment <-> Class distribution
assignment_classes = Table(
    "assignment_classes",
    BaseModel.metadata,
    Column("assignment_id", UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("class_id", UUID(as_uuid=True), ForeignKey("classes.id", ondelete="CASCADE"), primary_key=True)
)


# Association table for Assignment <-> Question with scoring
assignment_questions = Table(
    "assignment_questions",
    BaseModel.metadata,
    Column("assignment_id", UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True),
    Column("question_id", UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True),
    Column("points", Integer, nullable=False, default=1)
)


class StudentSubmission(BaseModel):
    """
    Student submission/response to an assignment.
    Supports both AI and teacher grading.
    """
    __tablename__ = "student_submissions"
    
    assignment_id = Column(UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    submitted_at = Column(DateTime, nullable=False)
    content_url = Column(Text, nullable=True)  # Audio file or PDF
    status = Column(ENUM(SubmissionStatus, name="submission_status"), nullable=False, default=SubmissionStatus.SUBMITTED)
    
    # Grading (supports both AI and teacher scoring)
    ai_score = Column(Numeric(5, 2), nullable=True)  # AI-generated score
    teacher_score = Column(Numeric(5, 2), nullable=True)  # Teacher override/manual score
    grade_score = Column(Numeric(5, 2), nullable=True)  # Final grade
    
    # Relationships
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User", back_populates="submissions")
    
    def __repr__(self) -> str:
        return f"<StudentSubmission {self.student_id} for {self.assignment_id}>"
