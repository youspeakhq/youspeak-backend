from typing import Dict, Optional
from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import get_logger

logger = get_logger(__name__)

from app.models.assessment import StudentSubmission, Assignment
from app.models.academic import class_enrollments
from app.models.analytics import Award, LearningSession
from app.models.user import User


class AnalyticsService:
    @staticmethod
    async def get_student_performance_analytics(
        db: AsyncSession,
        student_id: UUID,
        class_id: UUID,
    ) -> Optional[Dict]:
        """
        Aggregate performance metrics for a specific student in a class.
        """
        logger.info(
            "fetching_student_analytics",
            student_id=student_id,
            class_id=class_id
        )
        # Verify student is in class
        enrollment_stmt = select(class_enrollments).where(
            and_(
                class_enrollments.c.student_id == student_id,
                class_enrollments.c.class_id == class_id
            )
        )
        result = await db.execute(enrollment_stmt)
        if not result.first():
            return None

        # Student Name
        student = await db.get(User, student_id)
        student_name = f"{student.first_name or ''} {student.last_name or ''}".strip()

        # Overall Score and Submissions
        score_stmt = (
            select(
                func.avg(StudentSubmission.grade_score),
                func.count(StudentSubmission.id)
            )
            .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
            .where(
                and_(
                    StudentSubmission.student_id == student_id,
                    StudentSubmission.grade_score.isnot(None)
                )
            )
        )
        # Note: Ideally we filter by assignments belonging to the class_id
        # Need to join assignment_classes if present
        from app.models.assessment import assignment_classes
        score_stmt = score_stmt.join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id).where(
            assignment_classes.c.class_id == class_id
        )
        
        score_res = await db.execute(score_stmt)
        avg_score, total_submissions = score_res.fetchone()
        overall_score_pct = (float(avg_score) * 100.0) if avg_score is not None else 0.0

        # Topical Mastery (Mocked logic for now: using assignment titles as topics)
        # In a real app, Questions or assignments would have tags/topics.
        topic_stmt = (
            select(Assignment.title, func.avg(StudentSubmission.grade_score))
            .join(StudentSubmission, StudentSubmission.assignment_id == Assignment.id)
            .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
            .where(
                and_(
                    StudentSubmission.student_id == student_id,
                    assignment_classes.c.class_id == class_id,
                    StudentSubmission.grade_score.isnot(None)
                )
            )
            .group_by(Assignment.title)
        )
        topic_res = await db.execute(topic_stmt)
        topical_mastery = {row[0]: float(row[1]) * 100.0 for row in topic_res.all()}

        # Recent Scores (Last 5)
        recent_stmt = (
            select(StudentSubmission.grade_score)
            .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
            .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
            .where(
                and_(
                    StudentSubmission.student_id == student_id,
                    assignment_classes.c.class_id == class_id,
                    StudentSubmission.grade_score.isnot(None)
                )
            )
            .order_by(StudentSubmission.submitted_at.desc())
            .limit(5)
        )
        recent_res = await db.execute(recent_stmt)
        recent_scores = [float(row[0]) * 100.0 for row in recent_res.all()]

        # Awards Count
        awards_stmt = select(func.count(Award.id)).where(
            and_(
                Award.student_id == student_id,
                Award.class_id == class_id
            )
        )
        awards_count = (await db.execute(awards_stmt)).scalar() or 0

        # Engagement Score (Simulated from session participation)
        # Real logic would count events in sessions for this student
        engagement_score = 82.0 # Mocked

        # Last Activity
        last_act_stmt = select(func.max(StudentSubmission.submitted_at)).where(
            StudentSubmission.student_id == student_id
        )
        last_activity_at = (await db.execute(last_act_stmt)).scalar()

        return {
            "student_id": student_id,
            "student_name": student_name,
            "class_id": class_id,
            "overall_score_pct": round(overall_score_pct, 1),
            "total_submissions": total_submissions,
            "topical_mastery": {k: round(v, 1) for k, v in topical_mastery.items()},
            "recent_scores": [round(s, 1) for s in recent_scores],
            "awards_count": awards_count,
            "engagement_score": engagement_score,
            "last_activity_at": last_activity_at,
        }
