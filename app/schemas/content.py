from typing import Optional, List, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from app.models.enums import (
    AssignmentType, AssignmentStatus, QuestionType, SubmissionStatus,
    CurriculumSourceType, CurriculumStatus
)

class ClassBrief(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)

# --- Curriculum ---
class CurriculumCreate(BaseModel):
    title: str
    language_id: int
    description: Optional[str] = None
    source_type: CurriculumSourceType = CurriculumSourceType.TEACHER_UPLOAD
    class_ids: List[UUID] = []

class TopicCreate(BaseModel):
    title: str
    content: Optional[str] = None
    duration_hours: Optional[float] = None
    learning_objectives: List[str] = []
    order_index: int = 0

class TopicUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    duration_hours: Optional[float] = None
    learning_objectives: Optional[List[str]] = None
    order_index: Optional[int] = None

class TopicResponse(BaseModel):
    id: UUID
    title: str
    content: Optional[str] = None
    duration_hours: Optional[float] = None
    learning_objectives: List[str]
    order_index: int
    
    model_config = ConfigDict(from_attributes=True)

class CurriculumUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[CurriculumStatus] = None
    file_url: Optional[str] = None
    class_ids: Optional[List[UUID]] = None

class CurriculumMergeProposeRequest(BaseModel):
    library_curriculum_id: UUID

class TopicProposal(BaseModel):
    action: str # "keep", "blend", "replace", "add"
    source: str # "teacher", "library", "both"
    topic: TopicCreate # The proposed merged topic

class MergeProposalResponse(BaseModel):
    proposal_id: UUID # Could be a cache ID for the temporary proposal
    proposed_topics: List[TopicProposal]

class CurriculumMergeConfirmRequest(BaseModel):
    # The final list of topics the teacher has approved from the wizard
    final_topics: List[TopicCreate]

class CurriculumResponse(BaseModel): # Changed from CurriculumBase to BaseModel
    id: UUID
    title: str # Added from CurriculumBase
    description: Optional[str] = None # Added from CurriculumBase
    source_type: CurriculumSourceType # Added from CurriculumBase
    file_url: Optional[str] = None
    status: CurriculumStatus
    created_at: datetime
    language_name: Optional[str] = None
    classes: List[ClassBrief] = []
    topics: List[TopicResponse] = []
    
    model_config = ConfigDict(from_attributes=True)

class CurriculumGenerateRequest(BaseModel):
    prompt: str
    language_id: int

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
    
    model_config = ConfigDict(from_attributes=True)
