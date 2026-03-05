from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime, timezone

from app.models.enums import (
    TaskCategory, AssignmentType, AssignmentStatus, QuestionType, CurriculumSourceType,
    CurriculumStatus
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
    action: str  # "keep", "blend", "replace", "add"
    source: str  # "teacher", "library", "both"
    topic: TopicCreate  # The proposed merged topic


class MergeProposalResponse(BaseModel):
    proposal_id: UUID  # Could be a cache ID for the temporary proposal
    proposed_topics: List[TopicProposal]


class CurriculumMergeConfirmRequest(BaseModel):
    # The final list of topics the teacher has approved from the wizard
    final_topics: List[TopicCreate]


class CurriculumResponse(BaseModel):  # Changed from CurriculumBase to BaseModel
    id: UUID
    title: str  # Added from CurriculumBase
    description: Optional[str] = None  # Added from CurriculumBase
    source_type: CurriculumSourceType  # Added from CurriculumBase
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

# --- Marking ---


class MarkingCriterionItem(BaseModel):
    """One marking criterion (from curriculum extract-marking-scheme)."""
    criterion: str
    max_points: int
    description: Optional[str] = None


# --- Assessment ---


class QuestionBase(BaseModel):
    question_text: str
    type: QuestionType
    correct_answer: Optional[str] = None  # JSON string or text
    options: Optional[List[str]] = None  # For MC type, helper field


class AssessmentCreate(BaseModel):
    title: str
    category: TaskCategory = TaskCategory.ASSESSMENT  # "assessment" or "assignment"
    type: AssignmentType  # "oral" or "written"
    instructions: Optional[str] = None
    due_date: Optional[datetime] = None
    class_ids: List[UUID] = []
    enable_ai_marking: bool = False
    topics: Optional[List[str]] = None
    rubric_url: Optional[str] = None
    rubric_data: Optional[List[MarkingCriterionItem]] = None
    questions: Optional[List["AssignmentQuestionItem"]] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def normalize_due_date(cls, v):
        """Convert timezone-aware datetime to UTC naive datetime for PostgreSQL TIMESTAMP."""
        if v is None:
            return v
        if isinstance(v, str):
            # Parse ISO string (Pydantic will handle this, but we catch it here)
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is not None:
            # Convert to UTC and remove timezone info
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "title": "French Vocabulary Quiz",
                    "category": "assessment",
                    "type": "written",
                    "instructions": "Complete all questions carefully",
                    "due_date": "2026-03-20T23:59:59Z",
                    "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
                    "enable_ai_marking": True,
                    "questions": [
                        {
                            "question_id": "123e4567-e89b-12d3-a456-426614174000",
                            "points": 10
                        }
                    ]
                },
                {
                    "title": "Homework Reading Assignment",
                    "category": "assignment",
                    "type": "written",
                    "instructions": "Read chapter 5 and write a summary",
                    "due_date": "2026-04-01T23:59:59Z",
                    "class_ids": ["c1fbfe2a-dc95-4627-b355-5abedc2f1184"],
                    "enable_ai_marking": False
                }
            ]
        }
    )


class AssessmentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[TaskCategory] = None
    type: Optional[AssignmentType] = None
    instructions: Optional[str] = None
    due_date: Optional[datetime] = None
    class_ids: Optional[List[UUID]] = None
    enable_ai_marking: Optional[bool] = None
    topics: Optional[List[str]] = None
    rubric_url: Optional[str] = None
    rubric_data: Optional[List[MarkingCriterionItem]] = None

    @field_validator("due_date", mode="before")
    @classmethod
    def normalize_due_date(cls, v):
        """Convert timezone-aware datetime to UTC naive datetime for PostgreSQL TIMESTAMP."""
        if v is None:
            return v
        if isinstance(v, str):
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        if isinstance(v, datetime) and v.tzinfo is not None:
            return v.astimezone(timezone.utc).replace(tzinfo=None)
        return v


class AssessmentContentUpdate(BaseModel):
    questions: List[dict]  # {text, options, answer}


class AssessmentResponse(BaseModel):
    id: UUID
    title: str
    category: TaskCategory
    type: AssignmentType
    status: AssignmentStatus
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    enable_ai_marking: bool = False
    topics: Optional[List[str]] = None
    rubric_url: Optional[str] = None
    rubric_data: Optional[List[MarkingCriterionItem]] = None

    model_config = ConfigDict(from_attributes=True)


class AssessmentListRow(BaseModel):
    """One row for Task Management table: class-level or assignment-level."""
    id: UUID
    title: str
    category: TaskCategory  # "assessment" or "assignment" - shown in Type column in Figma
    type: AssignmentType  # "oral" or "written"
    status: AssignmentStatus
    due_date: Optional[datetime] = None
    class_name: Optional[str] = None
    active_students: Optional[int] = None
    task_topic: Optional[str] = None
    average_score: Optional[float] = None
    enable_ai_marking: bool = False

    model_config = ConfigDict(from_attributes=True)


class QuestionResponse(BaseModel):
    id: UUID
    question_text: str
    type: QuestionType
    correct_answer: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AssignmentQuestionItem(BaseModel):
    question_id: UUID
    points: int = 1


class SubmissionRow(BaseModel):
    """One row for Class students list: student, status, score."""
    id: UUID
    student_id: UUID
    student_name: Optional[str] = None
    status: str
    score_percent: Optional[float] = None
    submitted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionGradeUpdate(BaseModel):
    teacher_score: Optional[float] = None
    grade_score: Optional[float] = None
    ai_score: Optional[float] = None
    status: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_assessments: int
    total_assignments: int
    average_completion_rate: Optional[float] = None


class GenerateQuestionsRequest(BaseModel):
    """Request for Generate with AI (calls curriculum/Bedrock)."""
    topics: List[str]
    assignment_type: str = "written"  # oral | written


class GeneratedQuestion(BaseModel):
    """One AI-generated question (from curriculum service)."""
    question_text: str
    type: str  # multiple_choice | open_text | oral
    correct_answer: Optional[str] = None
    options: Optional[List[str]] = None



# Resolve forward reference in AssessmentCreate.questions
AssessmentCreate.model_rebuild()
