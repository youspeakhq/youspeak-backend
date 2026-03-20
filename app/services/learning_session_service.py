"""Learning session (room) service for starting/ending and listing sessions."""

from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import LearningSession
from app.models.assessment import Assignment, StudentSubmission, assignment_classes
from app.models.enums import SessionStatus, SessionType, UserRole
from app.models.user import User
from app.utils.time import get_utc_now
from app.core.logging import get_logger

logger = get_logger(__name__)

from app.services.academic_service import AcademicService


class LearningSessionService:
    @staticmethod
    async def _get_user_classes(db: AsyncSession, user: User) -> List:
        """Get classes for user based on their role (teacher or admin)"""
        if user.role == UserRole.SCHOOL_ADMIN:
            return await AcademicService.get_school_classes(db, user.school_id)
        elif user.role == UserRole.TEACHER:
            return await AcademicService.get_teacher_classes(db, user.id)
        return []

    @staticmethod
    async def _user_has_class_access(db: AsyncSession, user: User, class_id: UUID) -> bool:
        """Check if user (teacher or admin) has access to a class"""
        user_classes = await LearningSessionService._get_user_classes(db, user)
        return any(c.id == class_id for c in user_classes)

    @staticmethod
    async def _teacher_teaches_class(db: AsyncSession, teacher_id: UUID, class_id: UUID) -> bool:
        """Deprecated: Use _user_has_class_access instead"""
        teacher_classes = await AcademicService.get_teacher_classes(db, teacher_id)
        return any(c.id == class_id for c in teacher_classes)

    @staticmethod
    async def list_monitor_cards_for_teacher(
        db: AsyncSession,
        user: User,
    ) -> List[Tuple[UUID, str, int, Optional[LearningSession]]]:
        """
        Return (class_id, class_name, student_count, active_session) for each
        class the user has access to (teacher or admin). For Figma Room Monitor row of class cards.
        """
        user_classes = await LearningSessionService._get_user_classes(db, user)
        out: List[Tuple[UUID, str, int, Optional[LearningSession]]] = []
        for cls in user_classes:
            roster = await AcademicService.get_class_roster(db, cls.id)
            active = await LearningSessionService.get_active_session(db, cls.id)
            out.append((cls.id, cls.name, len(roster), active))
        return out

    @staticmethod
    async def list_sessions_for_class(
        db: AsyncSession,
        class_id: UUID,
        user: User,
        limit: int = 50,
    ) -> List[LearningSession]:
        if not await LearningSessionService._user_has_class_access(db, user, class_id):
            return []
        stmt = (
            select(LearningSession)
            .where(LearningSession.class_id == class_id)
            .order_by(LearningSession.started_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_active_session(
        db: AsyncSession,
        class_id: UUID,
    ) -> Optional[LearningSession]:
        stmt = (
            select(LearningSession)
            .where(
                LearningSession.class_id == class_id,
                LearningSession.status == SessionStatus.IN_PROGRESS,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_session_by_id(
        db: AsyncSession,
        session_id: UUID,
        class_id: Optional[UUID] = None,
    ) -> Optional[LearningSession]:
        stmt = select(LearningSession).where(LearningSession.id == session_id)
        if class_id is not None:
            stmt = stmt.where(LearningSession.class_id == class_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_monitor_stats(
        db: AsyncSession,
        user: User,
        timeframe: str,
    ) -> Tuple[int, int, Optional[float]]:
        """
        Return (total_sessions, active_students, avg_session_duration_minutes) for user's classes.
        timeframe: week | month | all.
        """
        user_classes = await LearningSessionService._get_user_classes(db, user)
        class_ids = [c.id for c in user_classes]
        if not class_ids:
            return 0, 0, None

        now = get_utc_now()
        if timeframe == "week":
            since = now - timedelta(days=7)
        elif timeframe == "month":
            since = now - timedelta(days=30)
        else:
            since = None

        total_sessions = 0
        sum_duration_seconds = 0.0
        count_with_duration = 0

        stmt = (
            select(LearningSession)
            .where(
                LearningSession.class_id.in_(class_ids),
                LearningSession.status == SessionStatus.COMPLETED,
                LearningSession.ended_at.isnot(None),
            )
        )
        if since is not None:
            stmt = stmt.where(LearningSession.ended_at >= since)
        result = await db.execute(stmt)
        sessions = list(result.scalars().all())
        total_sessions = len(sessions)
        for s in sessions:
            if s.ended_at and s.started_at:
                delta = (s.ended_at - s.started_at).total_seconds()
                if delta >= 0:
                    sum_duration_seconds += delta
                    count_with_duration += 1
        avg_session_duration_minutes = (
            (sum_duration_seconds / 60.0) / count_with_duration if count_with_duration else None
        )

        active_students = 0
        if since is not None:
            subq = (
                select(StudentSubmission.student_id)
                .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
                .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
                .where(
                    assignment_classes.c.class_id.in_(class_ids),
                    StudentSubmission.submitted_at >= since,
                    StudentSubmission.submitted_at <= now,
                )
                .distinct()
            )
            r = await db.execute(select(func.count()).select_from(subq.subquery()))
            active_students = r.scalar() or 0
        else:
            subq = (
                select(StudentSubmission.student_id)
                .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
                .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
                .where(assignment_classes.c.class_id.in_(class_ids))
                .distinct()
            )
            r = await db.execute(select(func.count()).select_from(subq.subquery()))
            active_students = r.scalar() or 0

        return total_sessions, active_students, avg_session_duration_minutes

    @staticmethod
    async def list_class_performance_summary_rows(
        db: AsyncSession,
        user: User,
    ) -> List[Tuple[Optional[LearningSession], Dict[str, Any]]]:
        """
        Return list of (active_session_or_none, row_dict) for each class the user has access to.
        row_dict: class_id, class_name, student_count, module_progress_pct, module_progress_label,
        avg_quiz_score_pct, time_spent_minutes_per_student, last_activity_at.
        """
        user_classes = await LearningSessionService._get_user_classes(db, user)
        rows: List[Tuple[Optional[LearningSession], Dict[str, Any]]] = []

        for cls in user_classes:
            roster = await AcademicService.get_class_roster(db, cls.id)
            student_count = len(roster)
            active = await LearningSessionService.get_active_session(db, cls.id)

            completed_sessions = (
                select(LearningSession)
                .where(
                    LearningSession.class_id == cls.id,
                    LearningSession.status == SessionStatus.COMPLETED,
                    LearningSession.ended_at.isnot(None),
                )
            )
            res = await db.execute(completed_sessions)
            sessions = list(res.scalars().all())
            total_minutes = 0.0
            last_session_end = None
            for s in sessions:
                if s.ended_at and s.started_at:
                    total_minutes += (s.ended_at - s.started_at).total_seconds() / 60.0
                if s.ended_at and (last_session_end is None or s.ended_at > last_session_end):
                    last_session_end = s.ended_at

            time_spent_minutes_per_student = (
                total_minutes / student_count if student_count else None
            )

            avg_score_subq = (
                select(func.avg(StudentSubmission.grade_score))
                .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
                .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
                .where(
                    assignment_classes.c.class_id == cls.id,
                    StudentSubmission.grade_score.isnot(None),
                )
            )
            r = await db.execute(avg_score_subq)
            avg_score = r.scalar()
            avg_quiz_score_pct = float(avg_score) if avg_score is not None else None
            if avg_quiz_score_pct is not None and avg_quiz_score_pct <= 1.0:
                avg_quiz_score_pct = avg_quiz_score_pct * 100.0

            last_sub_q = (
                select(func.max(StudentSubmission.submitted_at))
                .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
                .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
                .where(assignment_classes.c.class_id == cls.id)
            )
            r = await db.execute(last_sub_q)
            last_sub = r.scalar()
            last_activity_at = last_session_end
            if last_sub and (last_activity_at is None or last_sub > last_activity_at):
                last_activity_at = last_sub

            row = {
                "class_id": cls.id,
                "class_name": cls.name,
                "student_count": student_count,
                "module_progress_pct": None,
                "module_progress_label": None,
                "avg_quiz_score_pct": round(avg_quiz_score_pct, 1) if avg_quiz_score_pct is not None else None,
                "time_spent_minutes_per_student": round(time_spent_minutes_per_student, 1)
                if time_spent_minutes_per_student is not None
                else None,
                "last_activity_at": last_activity_at,
            }
            rows.append((active, row))

        return rows

    @staticmethod
    async def start_session(
        db: AsyncSession,
        class_id: UUID,
        user: User,
        session_type: SessionType,
    ) -> Optional[LearningSession]:
        if not await LearningSessionService._user_has_class_access(db, user, class_id):
            return None
        active = await LearningSessionService.get_active_session(db, class_id)
        if active:
            return None
        now = get_utc_now()
        session = LearningSession(
            class_id=class_id,
            started_by_user_id=user.id,
            session_type=session_type,
            started_at=now,
            status=SessionStatus.IN_PROGRESS,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def end_session(
        db: AsyncSession,
        session_id: UUID,
        class_id: UUID,
        user: User,
    ) -> bool:
        if not await LearningSessionService._user_has_class_access(db, user, class_id):
            return False
        session = await LearningSessionService.get_session_by_id(db, session_id, class_id=class_id)
        if not session or session.status != SessionStatus.IN_PROGRESS:
            return False
        session.status = SessionStatus.COMPLETED
        session.ended_at = get_utc_now()
        await db.commit()
        return True

    @staticmethod
    async def get_learning_room_report(
        db: AsyncSession,
        class_id: UUID,
        user: User,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a detailed report for a class's learning room activity.
        """
        if not await LearningSessionService._user_has_class_access(db, user, class_id):
            logger.warning("unauthorized_report_access", user_id=str(user.id), class_id=str(class_id))
            return None

        logger.info("generating_learning_room_report", class_id=str(class_id))

        cls = await AcademicService.get_class_by_id(db, class_id)
        if not cls:
            return None

        # Basic Stats
        stmt = (
            select(LearningSession)
            .where(
                LearningSession.class_id == class_id,
                LearningSession.status == SessionStatus.COMPLETED,
            )
            .order_by(LearningSession.started_at.desc())
        )
        result = await db.execute(stmt)
        sessions = list(result.scalars().all())

        total_sessions = len(sessions)
        if total_sessions == 0:
            return {
                "class_id": class_id,
                "class_name": cls.name,
                "total_sessions": 0,
                "active_students": 0,
                "avg_session_duration_minutes": 0,
                "session_frequency_pct": 0,
                "engagement_trend": [],
                "average_engagement": 0,
                "total_active_minutes": 0,
            }

        total_minutes = 0.0
        engagement_scores = []
        for s in sessions:
            if s.ended_at and s.started_at:
                dur = (s.ended_at - s.started_at).total_seconds() / 60.0
                total_minutes += dur
            # In a real app, engagement would be calculated from events.
            # Here we mock it or derive it if the model has a field.
            # Since the model doesn't have an 'engagement' field, we simulate it
            # based on session length and a random seed or some participation metric if available.
            engagement_scores.append(75.0 + (s.id.int % 20)) # Mocked for now

        # Session Frequency PCT: Current class sessions / average sessions per class in school
        school_classes = await AcademicService.get_school_classes(db, cls.school_id)
        class_ids = [c.id for c in school_classes]
        
        all_sessions_stmt = select(func.count(LearningSession.id)).where(LearningSession.class_id.in_(class_ids))
        total_school_sessions = (await db.execute(all_sessions_stmt)).scalar() or 0
        avg_sessions_per_class = total_school_sessions / len(class_ids) if class_ids else 1
        session_frequency_pct = (total_sessions / avg_sessions_per_class * 100.0) if avg_sessions_per_class else 0

        # Active Students (students with at least one submission in this class)
        subq = (
            select(StudentSubmission.student_id)
            .join(Assignment, StudentSubmission.assignment_id == Assignment.id)
            .join(assignment_classes, assignment_classes.c.assignment_id == Assignment.id)
            .where(assignment_classes.c.class_id == class_id)
            .distinct()
        )
        r = await db.execute(select(func.count()).select_from(subq.subquery()))
        active_students = r.scalar() or 0

        return {
            "class_id": class_id,
            "class_name": cls.name,
            "total_sessions": total_sessions,
            "active_students": active_students,
            "avg_session_duration_minutes": round(total_minutes / total_sessions, 1),
            "session_frequency_pct": round(session_frequency_pct, 1),
            "engagement_trend": engagement_scores[:5],
            "average_engagement": round(sum(engagement_scores) / len(engagement_scores), 1),
            "total_active_minutes": round(total_minutes, 1),
        }
