"""
Assessment management endpoints — teacher console only.
All routes require teacher auth and operate on the current teacher's data.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.schemas.content import (
    AssessmentCreate,
    AssessmentUpdate,
    AssessmentResponse,
    AssessmentListRow,
    QuestionBase,
    QuestionResponse,
    AssignmentQuestionItem,
    SubmissionRow,
    SubmissionGradeUpdate,
    AnalyticsSummary,
)
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta
from app.services.assessment_service import AssessmentService

router = APIRouter()


def _assignment_to_list_row(a, class_name: Optional[str] = None, active_students: Optional[int] = None, average_score: Optional[float] = None) -> dict:
    return {
        "id": a.id,
        "title": a.title,
        "type": a.type,
        "status": a.status,
        "due_date": a.due_date,
        "class_name": class_name,
        "active_students": active_students,
        "task_topic": None,
        "average_score": average_score,
    }


# Define /questions/bank before /{assignment_id} so "questions" is not parsed as UUID


@router.get("/questions/bank", response_model=PaginatedResponse[QuestionResponse])
async def list_question_bank(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List teacher's question bank."""
    skip = (page - 1) * page_size
    questions, total = await AssessmentService.list_questions(db, current_user.id, skip=skip, limit=page_size)
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[QuestionResponse.model_validate(q) for q in questions],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.post("/questions/bank", response_model=SuccessResponse[QuestionResponse])
async def create_question(
    body: QuestionBase,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create a question in the teacher's bank."""
    q = await AssessmentService.create_question(db, current_user.id, body)
    return SuccessResponse(data=QuestionResponse.model_validate(q), message="Question created")


@router.get("/analytics/summary", response_model=SuccessResponse[AnalyticsSummary])
async def get_analytics_summary(
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Task Performance Analytics: total assessments, total assignments, average completion rate."""
    summary = await AssessmentService.analytics_summary(db, current_user.id, class_id=class_id)
    return SuccessResponse(data=AnalyticsSummary(**summary))


@router.get("", response_model=PaginatedResponse[AssessmentListRow])
async def list_assessments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    class_id: Optional[UUID] = Query(None, description="Filter by class"),
    type_filter: Optional[str] = Query(None, alias="type", description="oral | written"),
    search: Optional[str] = Query(None, description="Search by title"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List assignments for the teacher (Task Management table)."""
    skip = (page - 1) * page_size
    assignments, total = await AssessmentService.list_assignments(
        db, current_user.id, class_id=class_id, type_filter=type_filter, search=search, skip=skip, limit=page_size
    )
    items = [_assignment_to_list_row(a) for a in assignments]
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[AssessmentListRow(**x) for x in items],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.post("", response_model=SuccessResponse[AssessmentResponse])
async def create_assessment(
    body: AssessmentCreate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Create a new assessment (draft). Teacher console."""
    assignment = await AssessmentService.create_assignment(db, current_user.id, body)
    return SuccessResponse(
        data=AssessmentResponse.model_validate(assignment),
        message="Assessment created successfully",
    )


@router.get("/{assignment_id}", response_model=SuccessResponse[AssessmentResponse])
async def get_assessment(
    assignment_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get one assessment. Teacher console."""
    assignment = await AssessmentService.get_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data=AssessmentResponse.model_validate(assignment))


@router.patch("/{assignment_id}", response_model=SuccessResponse[AssessmentResponse])
async def update_assessment(
    assignment_id: UUID,
    body: AssessmentUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Update an assessment (draft). Teacher console."""
    assignment = await AssessmentService.update_assignment(db, assignment_id, current_user.id, body)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data=AssessmentResponse.model_validate(assignment))


# --- Questions (assignment) ---

@router.get("/{assignment_id}/questions", response_model=SuccessResponse[List[dict]])
async def get_assignment_questions(
    assignment_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List questions attached to this assignment (Review generated questions)."""
    rows = await AssessmentService.get_questions_for_assignment(db, assignment_id, current_user.id)
    items = [
        {"question": QuestionResponse.model_validate(q), "points": pts}
        for q, pts in rows
    ]
    return SuccessResponse(data=items)


@router.put("/{assignment_id}/questions", response_model=SuccessResponse)
async def set_assignment_questions(
    assignment_id: UUID,
    body: List[AssignmentQuestionItem],
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Set questions on an assignment (with points). Teacher console."""
    ok = await AssessmentService.set_assignment_questions(db, assignment_id, current_user.id, body)
    if not ok:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return SuccessResponse(data={"updated": True}, message="Questions updated")


# --- Submissions (Class students list) ---

@router.get("/{assignment_id}/submissions", response_model=PaginatedResponse[SubmissionRow])
async def list_submissions(
    assignment_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, description="submitted | graded"),
    search: Optional[str] = Query(None, description="Search by student name"),
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """List submissions for an assignment (Students Performance table)."""
    assignment = await AssessmentService.get_assignment(db, assignment_id, current_user.id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    skip = (page - 1) * page_size
    rows, total = await AssessmentService.list_submissions(
        db, assignment_id, current_user.id, status_filter=status, search=search, skip=skip, limit=page_size
    )
    items = []
    for sub, student_name in rows:
        score_pct = float(sub.grade_score or sub.ai_score or 0) if (sub.grade_score is not None or sub.ai_score is not None) else None
        items.append(
            SubmissionRow(
                id=sub.id,
                student_id=sub.student_id,
                student_name=student_name,
                status=sub.status.value,
                score_percent=score_pct,
                submitted_at=sub.submitted_at,
            )
        )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=items,
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
    )


@router.get("/{assignment_id}/submissions/{submission_id}", response_model=SuccessResponse[dict])
async def get_submission(
    assignment_id: UUID,
    submission_id: UUID,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Get one submission (View Analytics). Teacher console."""
    sub = await AssessmentService.get_submission(db, assignment_id, submission_id, current_user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SuccessResponse(
        data={
            "id": str(sub.id),
            "student_id": str(sub.student_id),
            "assignment_id": str(sub.assignment_id),
            "status": sub.status.value,
            "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
            "ai_score": float(sub.ai_score) if sub.ai_score is not None else None,
            "teacher_score": float(sub.teacher_score) if sub.teacher_score is not None else None,
            "grade_score": float(sub.grade_score) if sub.grade_score is not None else None,
        }
    )


@router.patch("/{assignment_id}/submissions/{submission_id}/grade", response_model=SuccessResponse[dict])
async def grade_submission(
    assignment_id: UUID,
    submission_id: UUID,
    body: SubmissionGradeUpdate,
    current_user: User = Depends(deps.require_teacher),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """Update grade/status for a submission. Teacher console."""
    sub = await AssessmentService.grade_submission(db, assignment_id, submission_id, current_user.id, body)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    return SuccessResponse(
        data={
            "id": str(sub.id),
            "teacher_score": float(sub.teacher_score) if sub.teacher_score is not None else None,
            "grade_score": float(sub.grade_score) if sub.grade_score is not None else None,
            "status": sub.status.value,
        },
        message="Grade updated",
    )
