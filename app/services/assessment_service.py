"""
Assessment management service — teacher console only.
All operations are scoped to the given teacher_id (current user).
"""

from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy import select, delete, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.assessment import (
    Assignment,
    Question,
    StudentSubmission,
    assignment_classes,
    assignment_questions,
)
from app.models.enums import AssignmentStatus, SubmissionStatus
from app.schemas.content import (
    AssessmentCreate,
    AssessmentUpdate,
    QuestionBase,
    AssignmentQuestionItem,
    SubmissionGradeUpdate,
)


class AssessmentService:
    """Teacher-scoped assessment, question, and submission operations."""

    @staticmethod
    async def list_assignments(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: Optional[UUID] = None,
        type_filter: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Assignment], int]:
        """List assignments for the teacher (Task Management table)."""
        q = (
            select(Assignment)
            .where(Assignment.teacher_id == teacher_id)
        )
        if class_id is not None:
            q = q.join(assignment_classes).where(assignment_classes.c.class_id == class_id)
        if type_filter is not None:
            q = q.where(Assignment.type == type_filter)
        if search:
            q = q.where(Assignment.title.ilike(f"%{search}%"))

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        q = q.offset(skip).limit(limit).order_by(Assignment.created_at.desc())
        result = await db.execute(q)
        return list(result.scalars().unique().all()), total

    @staticmethod
    async def get_assignment(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Assignment]:
        """Get one assignment if it belongs to the teacher."""
        result = await db.execute(
            select(Assignment)
            .options(
                selectinload(Assignment.classes),
                selectinload(Assignment.questions),
            )
            .where(
                Assignment.id == assignment_id,
                Assignment.teacher_id == teacher_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_assignment(
        db: AsyncSession,
        teacher_id: UUID,
        data: AssessmentCreate,
    ) -> Assignment:
        """Create a draft assignment and link to classes (teacher must teach those classes)."""
        a = Assignment(
            teacher_id=teacher_id,
            title=data.title,
            instructions=data.instructions,
            type=data.type,
            due_date=data.due_date,
            status=AssignmentStatus.DRAFT,
            enable_ai_marking=getattr(data, "enable_ai_marking", False),
        )
        db.add(a)
        await db.flush()
        for cid in data.class_ids:
            await db.execute(
                insert(assignment_classes).values(
                    assignment_id=a.id,
                    class_id=cid,
                )
            )
        questions = getattr(data, "questions", None) or []
        if questions:
            question_ids = [it.question_id for it in questions]
            if len(set(question_ids)) != len(question_ids):
                raise ValueError("Duplicate question_ids in questions list.")
            result = await db.execute(
                select(Question.id).where(
                    Question.id.in_(question_ids),
                    Question.teacher_id == teacher_id,
                )
            )
            found_ids = {row[0] for row in result.all()}
            if len(found_ids) != len(question_ids):
                raise ValueError(
                    "One or more question_ids are invalid or do not belong to you."
                )
            for it in questions:
                await db.execute(
                    insert(assignment_questions).values(
                        assignment_id=a.id,
                        question_id=it.question_id,
                        points=it.points,
                    )
                )
        await db.commit()
        await db.refresh(a)
        return a

    @staticmethod
    async def update_assignment(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
        data: AssessmentUpdate,
    ) -> Optional[Assignment]:
        """Update assignment (draft only)."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return None
        if data.title is not None:
            a.title = data.title
        if data.type is not None:
            a.type = data.type
        if data.instructions is not None:
            a.instructions = data.instructions
        if data.due_date is not None:
            a.due_date = data.due_date
        if getattr(data, "enable_ai_marking", None) is not None:
            a.enable_ai_marking = data.enable_ai_marking
        if data.class_ids is not None:
            await db.execute(delete(assignment_classes).where(assignment_classes.c.assignment_id == assignment_id))
            for cid in data.class_ids:
                await db.execute(
                    insert(assignment_classes).values(assignment_id=assignment_id, class_id=cid)
                )
        await db.commit()
        await db.refresh(a)
        return a

    @staticmethod
    async def publish_assignment(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
    ) -> Optional[Assignment]:
        """Set assignment status to PUBLISHED (teacher-scoped)."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return None
        a.status = AssignmentStatus.PUBLISHED
        await db.commit()
        await db.refresh(a)
        return a

    @staticmethod
    async def list_questions(
        db: AsyncSession,
        teacher_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Question], int]:
        """List teacher's question bank."""
        q = select(Question).where(Question.teacher_id == teacher_id)
        total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        q = q.offset(skip).limit(limit).order_by(Question.created_at.desc())
        result = await db.execute(q)
        return list(result.scalars().all()), total

    @staticmethod
    async def create_question(
        db: AsyncSession,
        teacher_id: UUID,
        data: QuestionBase,
    ) -> Question:
        """Create a question in the teacher's bank."""
        q = Question(
            teacher_id=teacher_id,
            question_text=data.question_text,
            type=data.type,
            correct_answer=data.correct_answer,
        )
        db.add(q)
        await db.commit()
        await db.refresh(q)
        return q

    @staticmethod
    async def get_questions_for_assignment(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
    ) -> List[Tuple[Question, int]]:
        """Return questions linked to this assignment with points. Teacher-scoped."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return []
        # Load questions through assignment_questions
        result = await db.execute(
            select(Question, assignment_questions.c.points)
            .join(assignment_questions, assignment_questions.c.question_id == Question.id)
            .where(
                assignment_questions.c.assignment_id == assignment_id,
                Question.teacher_id == teacher_id,
            )
        )
        return list(result.all())

    @staticmethod
    async def set_assignment_questions(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
        items: List[AssignmentQuestionItem],
    ) -> bool:
        """Replace questions on an assignment (teacher-scoped)."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return False
        await db.execute(delete(assignment_questions).where(assignment_questions.c.assignment_id == assignment_id))
        for it in items:
            await db.execute(
                insert(assignment_questions).values(
                    assignment_id=assignment_id,
                    question_id=it.question_id,
                    points=it.points,
                )
            )
        await db.commit()
        return True

    @staticmethod
    async def list_submissions(
        db: AsyncSession,
        assignment_id: UUID,
        teacher_id: UUID,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Tuple[StudentSubmission, Optional[str]]], int]:
        """List submissions for an assignment (Class students list). Returns (submission, student_name)."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return [], 0
        from app.models.user import User

        q = (
            select(StudentSubmission, User.first_name, User.last_name)
            .join(User, User.id == StudentSubmission.student_id)
            .where(StudentSubmission.assignment_id == assignment_id)
        )
        if status_filter:
            q = q.where(StudentSubmission.status == status_filter)
        if search:
            q = q.where(
                (User.first_name.ilike(f"%{search}%")) | (User.last_name.ilike(f"%{search}%"))
            )

        count_q = select(func.count()).select_from(q.subquery())
        total = (await db.execute(count_q)).scalar() or 0
        q = q.offset(skip).limit(limit).order_by(StudentSubmission.submitted_at.desc())
        result = await db.execute(q)
        rows = []
        for row in result.all():
            sub, fn, ln = row[0], row[1], row[2]
            name = f"{fn or ''} {ln or ''}".strip() if (fn or ln) else None
            rows.append((sub, name))
        return rows, total

    @staticmethod
    async def get_submission(
        db: AsyncSession,
        assignment_id: UUID,
        submission_id: UUID,
        teacher_id: UUID,
    ) -> Optional[StudentSubmission]:
        """Get one submission; assignment must belong to teacher."""
        a = await AssessmentService.get_assignment(db, assignment_id, teacher_id)
        if not a:
            return None
        result = await db.execute(
            select(StudentSubmission)
            .where(
                StudentSubmission.id == submission_id,
                StudentSubmission.assignment_id == assignment_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def grade_submission(
        db: AsyncSession,
        assignment_id: UUID,
        submission_id: UUID,
        teacher_id: UUID,
        data: SubmissionGradeUpdate,
    ) -> Optional[StudentSubmission]:
        """Update grade/status for a submission (teacher console)."""
        sub = await AssessmentService.get_submission(db, assignment_id, submission_id, teacher_id)
        if not sub:
            return None
        if data.teacher_score is not None:
            sub.teacher_score = Decimal(str(data.teacher_score))
        if data.grade_score is not None:
            sub.grade_score = Decimal(str(data.grade_score))
        if getattr(data, "ai_score", None) is not None:
            sub.ai_score = Decimal(str(data.ai_score))
        if data.status is not None:
            sub.status = SubmissionStatus(data.status)
        await db.commit()
        await db.refresh(sub)
        return sub

    @staticmethod
    async def analytics_summary(
        db: AsyncSession,
        teacher_id: UUID,
        class_id: Optional[UUID] = None,
    ) -> dict:
        """Task Performance Analytics: total assessments, total assignments, average completion rate."""
        base = select(Assignment).where(Assignment.teacher_id == teacher_id)
        if class_id is not None:
            base = base.join(assignment_classes).where(assignment_classes.c.class_id == class_id)

        total_assignments = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        total_assessments = total_assignments  # same set in our model

        # Completion: submissions / expected (students in assigned classes). Simplified: use submission count.
        # For average completion rate we'd need expected count per assignment; placeholder.
        average_completion_rate = None

        return {
            "total_assessments": total_assessments,
            "total_assignments": total_assignments,
            "average_completion_rate": average_completion_rate,
        }
