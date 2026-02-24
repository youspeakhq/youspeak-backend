"""Internal curriculum API routes (require X-School-Id)."""

import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from api.deps import get_school_id
from services.curriculum_service import CurriculumService
from schemas.content import (
    CurriculumCreate,
    CurriculumUpdate,
    CurriculumResponse,
    TopicResponse,
    TopicUpdate,
    CurriculumGenerateRequest,
    CurriculumMergeProposeRequest,
    CurriculumMergeConfirmRequest,
    MergeProposalResponse,
)
from schemas.responses import SuccessResponse, PaginatedResponse
from models.enums import CurriculumStatus

router = APIRouter()


def _curriculum_to_response(c) -> CurriculumResponse:
    return CurriculumResponse(
        id=c.id,
        title=c.title,
        description=c.description,
        source_type=c.source_type,
        file_url=c.file_url,
        status=c.status,
        created_at=c.created_at,
        language_name=c.language.name if c.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in c.classes],
        topics=[
            TopicResponse(
                id=t.id,
                title=t.title,
                content=t.content,
                duration_hours=t.duration_hours,
                learning_objectives=t.learning_objectives,
                order_index=t.order_index,
            )
            for t in (getattr(c, "topics", None) or [])
        ],
    )


@router.get("", response_model=PaginatedResponse[CurriculumResponse])
async def list_curriculums(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[CurriculumStatus] = Query(None),
    language_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    skip = (page - 1) * page_size
    curriculums, total = await CurriculumService.get_curriculums(
        db,
        school_id,
        skip=skip,
        limit=page_size,
        status=status,
        language_id=language_id,
        search=search,
    )
    serialized = [_curriculum_to_response(c) for c in curriculums]
    total_pages = (total + page_size - 1) // page_size
    return PaginatedResponse(
        data=serialized,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.post("", response_model=SuccessResponse[CurriculumResponse])
async def create_curriculum(
    body: CurriculumCreate,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    new_curriculum = await CurriculumService.create_curriculum(db, school_id, body)
    return SuccessResponse(
        data=_curriculum_to_response(new_curriculum),
        message="Curriculum uploaded successfully",
    )


@router.post("/generate", response_model=SuccessResponse[List[TopicResponse]])
async def generate_curriculum(
    body: CurriculumGenerateRequest,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    topics_create = await CurriculumService.generate_curriculum_topics(
        db, body.prompt, body.language_id
    )
    data = [
        TopicResponse(
            id=uuid.uuid4(),
            title=t.title,
            content=t.content,
            duration_hours=t.duration_hours,
            learning_objectives=t.learning_objectives,
            order_index=t.order_index,
        )
        for t in topics_create
    ]
    return SuccessResponse(data=data, message="Curriculum generated successfully")


@router.patch("/topics/{topic_id}", response_model=SuccessResponse[TopicResponse])
async def update_topic(
    topic_id: uuid.UUID,
    body: TopicUpdate,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    updated = await CurriculumService.update_topic(db, topic_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Topic not found")
    return SuccessResponse(
        data=TopicResponse(
            id=updated.id,
            title=updated.title,
            content=updated.content,
            duration_hours=updated.duration_hours,
            learning_objectives=updated.learning_objectives,
            order_index=updated.order_index,
        ),
        message="Topic updated successfully",
    )


@router.get("/{curriculum_id}", response_model=SuccessResponse[CurriculumResponse])
async def get_curriculum(
    curriculum_id: uuid.UUID,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    curriculum = await CurriculumService.get_curriculum_by_id(
        db, curriculum_id, school_id
    )
    if not curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return SuccessResponse(data=_curriculum_to_response(curriculum))


@router.patch("/{curriculum_id}", response_model=SuccessResponse[CurriculumResponse])
async def update_curriculum(
    curriculum_id: uuid.UUID,
    body: CurriculumUpdate,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    updated = await CurriculumService.update_curriculum(
        db, curriculum_id, school_id, body
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return SuccessResponse(
        data=_curriculum_to_response(updated),
        message="Curriculum updated successfully",
    )


@router.delete("/{curriculum_id}", response_model=SuccessResponse)
async def delete_curriculum(
    curriculum_id: uuid.UUID,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    success = await CurriculumService.delete_curriculum(db, curriculum_id, school_id)
    if not success:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return SuccessResponse(data=None, message="Curriculum deleted successfully")


@router.post("/{curriculum_id}/extract", response_model=SuccessResponse[List[TopicResponse]])
async def extract_topics(
    curriculum_id: uuid.UUID,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    curriculum = await CurriculumService.get_curriculum_by_id(
        db, curriculum_id, school_id
    )
    if not curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    if not curriculum.file_url:
        raise HTTPException(
            status_code=400, detail="Curriculum has no document to extract from"
        )
    topics = await CurriculumService.extract_topics(
        db, curriculum_id, curriculum.file_url
    )
    data = [
        TopicResponse(
            id=t.id,
            title=t.title,
            content=t.content,
            duration_hours=t.duration_hours,
            learning_objectives=t.learning_objectives,
            order_index=t.order_index,
        )
        for t in topics
    ]
    return SuccessResponse(data=data, message="Topics extracted successfully")


@router.post(
    "/{curriculum_id}/merge/propose",
    response_model=SuccessResponse[MergeProposalResponse],
)
async def propose_merge(
    curriculum_id: uuid.UUID,
    body: CurriculumMergeProposeRequest,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    teacher_curriculum = await CurriculumService.get_curriculum_by_id(
        db, curriculum_id, school_id
    )
    library_curriculum = await CurriculumService.get_curriculum_by_id(
        db, body.library_curriculum_id, school_id
    )
    if not teacher_curriculum or not library_curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    proposals = await CurriculumService.propose_merge_strategy(
        db, teacher_curriculum, library_curriculum
    )
    return SuccessResponse(
        data=MergeProposalResponse(
            proposal_id=uuid.uuid4(),
            proposed_topics=proposals,
        ),
        message="Merge proposal generated",
    )


@router.post("/{curriculum_id}/merge/confirm", response_model=SuccessResponse[CurriculumResponse])
async def confirm_merge(
    curriculum_id: uuid.UUID,
    body: CurriculumMergeConfirmRequest,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    merged = await CurriculumService.confirm_merge(
        db, school_id, curriculum_id, body.final_topics
    )
    return SuccessResponse(
        data=_curriculum_to_response(merged),
        message="Curriculum merged successfully",
    )
