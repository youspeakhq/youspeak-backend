from typing import Optional, List, Union, Any
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from app.models.enums import (
    AssignmentType, AssignmentStatus, QuestionType, SubmissionStatus,
    CurriculumSourceType, CurriculumStatus
)

# --- Curriculum ---
class CurriculumBase(BaseModel):
    title: str
    description: Optional[str] = None
    source_type: CurriculumSourceType

class CurriculumUpload(BaseModel):
    # File upload handled via Multipart
    pass

class CurriculumMergeRequest(BaseModel):
    source_id: UUID
    library_ids: List[UUID]
    strategy: str = "append"

class CurriculumResponse(CurriculumBase):
    id: UUID
    file_url: Optional[str] = None
    status: CurriculumStatus
    created_at: datetime
    
    class Config:
        from_attributes = True

class AIGenerateRequest(BaseModel):
    topics: List[str]
    count: int = 10

# --- Assessment ---
class QuestionBase(BaseModel):
    question_text: str
    type: QuestionType
    correct_answer: Optional[str] = None # JSON string or text
    options: Optional[List[str]] = None # For MC type, helper field

class AssessmentCreate(BaseModel):
    title: str
    type: AssignmentType
    due_date: Optional[datetime] = None
    class_ids: List[UUID] = []

class AssessmentContentUpdate(BaseModel):
    questions: List[dict] # {text, options, answer}

class AssessmentResponse(BaseModel):
    id: UUID
    title: str
    type: AssignmentType
    status: AssignmentStatus
    due_date: Optional[datetime]
    
    class Config:
        from_attributes = True
