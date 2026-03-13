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
    ParseDocumentRequest,
    ParseDocumentResponse,
    ExtractQuestionsRequest,
    ExtractQuestionsResponse,
    ExtractMarkingSchemeRequest,
    ExtractMarkingSchemeResponse,
    GenerateAssessmentQuestionsRequest,
    ExtractedQuestion,
    EvaluateSubmissionRequest,
    EvaluateSubmissionResponse,
)
from schemas.responses import SuccessResponse, PaginatedResponse
from models.enums import CurriculumStatus, CurriculumSourceType

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
    source_type: Optional[CurriculumSourceType] = Query(None, description="Filter by source: library_master, teacher_upload, or merged"),
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
        source_type=source_type,
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


@router.post("/parse-document", response_model=SuccessResponse[ParseDocumentResponse])
async def parse_document(
    body: ParseDocumentRequest,
) -> Any:
    """Parse a document (URL) to markdown. Reusable for curriculum and assessment uploads."""
    from utils.document_parser import parse_document_to_markdown

    markdown = await parse_document_to_markdown(body.file_url)
    return SuccessResponse(data=ParseDocumentResponse(markdown=markdown), message="Document parsed")


@router.post("/assessment-questions/generate", response_model=SuccessResponse[List[ExtractedQuestion]])
async def generate_assessment_questions(
    body: GenerateAssessmentQuestionsRequest,
) -> Any:
    """Generate with AI: produce assessment questions from topics (Bedrock)."""
    try:
        questions = await CurriculumService.generate_assessment_questions(
            topics=body.topics,
            assignment_type=body.assignment_type or "written",
            num_questions=body.num_questions,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI generation unavailable: {getattr(e, 'message', str(e))}",
        )
    return SuccessResponse(data=questions, message="Questions generated")


@router.post("/evaluate-submission", response_model=SuccessResponse[EvaluateSubmissionResponse])
async def evaluate_submission(
    body: EvaluateSubmissionRequest,
) -> Any:
    """Mark with AI: score a submission (Bedrock)."""
    questions_dict = [
        {"question_text": q.question_text, "points": q.points, "correct_answer": q.correct_answer}
        for q in body.questions
    ]
    criteria_dict = (
        [{"criterion": c.criterion, "max_points": c.max_points, "description": c.description} for c in body.marking_criteria]
        if body.marking_criteria
        else None
    )
    try:
        result = await CurriculumService.evaluate_submission(
            instructions=body.instructions,
            questions=questions_dict,
            submission_markdown=body.submission_markdown,
            marking_criteria=criteria_dict,
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI evaluation unavailable: {getattr(e, 'message', str(e))}",
        )
    return SuccessResponse(data=result, message="Submission evaluated")


@router.post("/extract-questions", response_model=SuccessResponse[ExtractQuestionsResponse])
async def extract_questions_from_document(
    body: ExtractQuestionsRequest,
) -> Any:
    """Extract questions from document markdown (Upload questions manually)."""
    try:
        questions = await CurriculumService.extract_questions_from_markdown(body.markdown)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI extraction unavailable: {getattr(e, 'message', str(e))}",
        )
    return SuccessResponse(
        data=ExtractQuestionsResponse(questions=questions),
        message="Questions extracted",
    )


@router.post("/extract-marking-scheme", response_model=SuccessResponse[ExtractMarkingSchemeResponse])
async def extract_marking_scheme_from_document(
    body: ExtractMarkingSchemeRequest,
) -> Any:
    """Extract marking scheme from document markdown (Upload marking scheme)."""
    try:
        criteria = await CurriculumService.extract_marking_scheme_from_markdown(body.markdown)
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI extraction unavailable: {getattr(e, 'message', str(e))}",
        )
    return SuccessResponse(
        data=ExtractMarkingSchemeResponse(criteria=criteria),
        message="Marking scheme extracted",
    )


@router.post("/generate", response_model=SuccessResponse[List[TopicResponse]])
async def generate_curriculum(
    body: CurriculumGenerateRequest,
    school_id: uuid.UUID = Depends(get_school_id),
    db: AsyncSession = Depends(get_db),
) -> Any:
    try:
        topics_create = await CurriculumService.generate_curriculum_topics(
            db, body.prompt, body.language_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI generation unavailable: {getattr(e, 'message', str(e))}",
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
    try:
        topics = await CurriculumService.extract_topics(
            db, curriculum_id, curriculum.file_url
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI extraction unavailable: {getattr(e, 'message', str(e))}",
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
    try:
        proposals = await CurriculumService.propose_merge_strategy(
            db, teacher_curriculum, library_curriculum
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI merge proposal unavailable: {getattr(e, 'message', str(e))}",
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
    try:
        merged = await CurriculumService.confirm_merge(
            db, school_id, curriculum_id, body.final_topics
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"AI merge unavailable: {getattr(e, 'message', str(e))}",
        )
    return SuccessResponse(
        data=_curriculum_to_response(merged),
        message="Curriculum merged successfully",
    )
