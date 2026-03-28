"""Curriculum request/response schemas."""

from typing import Optional, List, Literal
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from models.enums import CurriculumSourceType, CurriculumStatus


class ClassBrief(BaseModel):
    id: UUID
    name: str

    model_config = ConfigDict(from_attributes=True)


class CurriculumCreate(BaseModel):
    title: str
    language_id: int
    description: Optional[str] = None
    source_type: CurriculumSourceType = CurriculumSourceType.TEACHER_UPLOAD
    class_ids: List[UUID] = []
    file_url: Optional[str] = None


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
    source_type: Optional[CurriculumSourceType] = None
    file_url: Optional[str] = None
    class_ids: Optional[List[UUID]] = None


class CurriculumMergeProposeRequest(BaseModel):
    library_curriculum_id: UUID


class TopicProposal(BaseModel):
    action: str = Field(..., description="Action for the topic: 'keep', 'blend', 'replace', or 'add'")
    source: str = Field(..., description="Source of the topic: 'teacher', 'library', or 'both'")
    topic: TopicCreate = Field(..., description="The full topic object containing title, content, duration, and objectives")


class MergeProposalResponse(BaseModel):
    proposal_id: UUID
    proposed_topics: List[TopicProposal]


class CurriculumMergeConfirmRequest(BaseModel):
    final_topics: List[TopicCreate]


class CurriculumResponse(BaseModel):
    id: UUID
    title: str
    description: Optional[str] = None
    source_type: CurriculumSourceType
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


# --- Document parsing (reusable: curriculum + assessment) ---


class ParseDocumentRequest(BaseModel):
    file_url: str


class ParseDocumentResponse(BaseModel):
    markdown: str


class ExtractedQuestion(BaseModel):
    question_text: str
    type: str  # "multiple_choice" | "open_text" | "oral"
    correct_answer: Optional[str] = None
    options: Optional[List[str]] = None


class ExtractQuestionsRequest(BaseModel):
    markdown: str


class ExtractQuestionsResponse(BaseModel):
    questions: List[ExtractedQuestion]


class MarkingCriterion(BaseModel):
    criterion: str
    max_points: int
    description: Optional[str] = None


class ExtractMarkingSchemeRequest(BaseModel):
    markdown: str


class ExtractMarkingSchemeResponse(BaseModel):
    criteria: List[MarkingCriterion]


class GenerateAssessmentQuestionsRequest(BaseModel):
    topics: List[str]
    assignment_type: Literal["written", "multiple_choice", "mixed", "oral"] = "multiple_choice"
    num_questions: int = Field(default=10, ge=1, le=20, description="Number of questions to generate (1-20)")


class QuestionForEvaluation(BaseModel):
    question_text: str
    points: int = 1
    correct_answer: Optional[str] = None


class EvaluateSubmissionRequest(BaseModel):
    instructions: Optional[str] = None
    questions: List[QuestionForEvaluation]
    submission_markdown: str
    marking_criteria: Optional[List[MarkingCriterion]] = None


class EvaluateSubmissionResponse(BaseModel):
    score: float  # 0–100 or 0–total_points; normalize in caller if needed
    feedback: Optional[str] = None
