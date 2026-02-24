"""Curriculum request/response schemas."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict

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
    file_url: Optional[str] = None
    class_ids: Optional[List[UUID]] = None


class CurriculumMergeProposeRequest(BaseModel):
    library_curriculum_id: UUID


class TopicProposal(BaseModel):
    action: str
    source: str
    topic: TopicCreate


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
