from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from collections import defaultdict
from decimal import Decimal

from app.utils.time import get_utc_now
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.onboarding import School, Language, school_languages
from app.models.user import User
from app.models.enums import UserRole, ClassStatus
from app.models.academic import Class, Semester, Classroom
from app.models.arena import Arena, ArenaPerformer
from app.schemas.school import SchoolCreate, SchoolUpdate
from app.schemas.admin import (
    LeaderboardResponse,
    LeaderboardStudentEntry,
    LeaderboardClassEntry,
)
from app.services.user_service import UserService


class SchoolService:
    """Service layer for School operations"""

    @staticmethod
    async def get_school_by_id(db: AsyncSession, school_id: UUID) -> Optional[School]:
        result = await db.execute(
            select(School).where(School.id == school_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_school_with_languages(db: AsyncSession, school_id: UUID) -> Optional[School]:
        """Fetch school with languages relationship loaded (for profile response)."""
        result = await db.execute(
            select(School)
            .where(School.id == school_id)
            .options(selectinload(School.languages))
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_school_with_admin(
        db: AsyncSession,
        school_data: SchoolCreate,
        admin_data: Dict[str, str]
    ) -> School:
        """
        Create a new school and its first admin user transactionally.
        """
        # Create School
        school = School(
            name=school_data.name,
            school_type=school_data.school_type,
            program_type=school_data.program_type,
            address_country=school_data.address_country,
            address_state=school_data.address_state,
            address_city=school_data.address_city,
            address_zip=school_data.address_zip,
            is_active=True
        )
        db.add(school)
        await db.flush()  # Flush to get school.id

        # Create Admin User
        # Create Admin User
        await UserService.create_user(
            db=db,
            email=admin_data["email"],
            password=admin_data["password"],
            first_name=admin_data["first_name"],
            last_name=admin_data["last_name"],
            role=UserRole.SCHOOL_ADMIN,
            school_id=school.id
        )

        # Create Default Semester
        default_semester = Semester(
             school_id=school.id,
             name="Term 1",
             start_date=get_utc_now(),
             end_date=get_utc_now() + timedelta(days=90),
             is_active=True
        )
        db.add(default_semester)

        # Seed Languages if empty
        stmt = select(Language).limit(1)
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            languages = [
                Language(code="en", name="English"),
                Language(code="es", name="Spanish"),
                Language(code="fr", name="French")
            ]
            db.add_all(languages)

        await db.commit()
        await db.refresh(school)
        return school

    @staticmethod
    async def update_school(
        db: AsyncSession,
        school_id: UUID,
        school_update: SchoolUpdate
    ) -> Optional[School]:
        school = await SchoolService.get_school_by_id(db, school_id)
        if not school:
            return None

        update_data = school_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(school, field, value)

        await db.flush()
        await db.commit()
        await db.refresh(school)
        return school

    @staticmethod
    async def get_stats(db: AsyncSession, school_id: UUID) -> Dict[str, int]:
        """
        Get aggregated stats for admin dashboard.
        """
        # Active Classes
        classes_query = select(func.count(Class.id)).where(
            Class.school_id == school_id,
            Class.status == ClassStatus.ACTIVE
        )
        classes_count = await db.scalar(classes_query)

        # Total Students
        students_query = select(func.count(User.id)).where(
            User.school_id == school_id,
            User.role == UserRole.STUDENT,
            User.is_active.is_(True),
            User.deleted_at.is_(None)
        )
        students_count = await db.scalar(students_query)

        # Total Teachers
        teachers_query = select(func.count(User.id)).where(
            User.school_id == school_id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
            User.deleted_at.is_(None)
        )
        teachers_count = await db.scalar(teachers_query)

        return {
            "active_classes": classes_count or 0,
            "total_students": students_count or 0,
            "total_teachers": teachers_count or 0
        }

    @staticmethod
    async def update_programs(db: AsyncSession, school_id: UUID, language_codes: List[str]) -> bool:
        """Update languages offered by school.
        Uses selectinload to avoid async lazy-load when assigning many-to-many.
        Returns False if school not found or any language code is not in the languages table.
        """
        stmt = (
            select(School)
            .where(School.id == school_id)
            .options(selectinload(School.languages))
        )
        result = await db.execute(stmt)
        school = result.scalar_one_or_none()
        if not school:
            return False

        stmt = select(Language).where(Language.code.in_(language_codes))
        result = await db.execute(stmt)
        languages = result.scalars().all()
        found_codes = {lang.code for lang in languages}
        if found_codes != set(language_codes):
            return False

        school.languages = list(languages)
        await db.flush()
        return True

    @staticmethod
    async def remove_program(db: AsyncSession, school_id: UUID, language_code: str) -> bool:
        """Remove one language from school's offered languages.
        Returns False if language not in DB or not offered by school."""
        lang_stmt = select(Language).where(Language.code == language_code)
        lang_result = await db.execute(lang_stmt)
        language = lang_result.scalar_one_or_none()
        if not language:
            return False

        stmt = (
            select(School)
            .where(School.id == school_id)
            .options(selectinload(School.languages))
        )
        result = await db.execute(stmt)
        school = result.scalar_one_or_none()
        if not school:
            return False

        if language not in school.languages:
            return False

        school.languages = [lang for lang in school.languages if lang.code != language_code]
        await db.flush()
        return True

    @staticmethod
    async def get_semesters(db: AsyncSession, school_id: UUID) -> List[Semester]:
        """Get all semesters for school"""
        stmt = (
            select(Semester)
            .where(Semester.school_id == school_id)
            .order_by(desc(Semester.start_date))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_leaderboard(
        db: AsyncSession,
        school_id: UUID,
        timeframe: str = "week",
        class_ids: Optional[List[UUID]] = None,
    ) -> LeaderboardResponse:
        """
        Top students and top classes by arena points (Figma: Students leaderboard + top classes).
        Timeframe filters Arena.start_time: week (7d), month (30d), all (no filter).
        When class_ids is set, restrict to those classes (e.g. teacher-scoped leaderboard).
        """
        since: Optional[datetime] = None
        if timeframe == "week":
            since = get_utc_now() - timedelta(days=7)
        elif timeframe == "month":
            since = get_utc_now() - timedelta(days=30)

        arena_filter = Arena.class_id == Class.id
        if since is not None:
            arena_filter = and_(arena_filter, Arena.start_time >= since)

        base_where = [
            Class.school_id == school_id,
            User.school_id == school_id,
            User.role == UserRole.STUDENT,
            User.deleted_at.is_(None),
            arena_filter,
        ]
        if class_ids is not None:
            base_where.append(Class.id.in_(class_ids))

        # Student-class-points: (user_id, first_name, last_name, class_id, class_name, sub_class, points)
        student_pts = (
            select(
                User.id.label("user_id"),
                User.first_name,
                User.last_name,
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.sub_class,
                func.coalesce(func.sum(ArenaPerformer.total_points), 0).label("points"),
            )
            .select_from(User)
            .join(ArenaPerformer, ArenaPerformer.user_id == User.id)
            .join(Arena, Arena.id == ArenaPerformer.arena_id)
            .join(Class, Class.id == Arena.class_id)
            .where(and_(*base_where))
            .group_by(User.id, User.first_name, User.last_name, Class.id, Class.name, Class.sub_class)
        )
        result = await db.execute(student_pts)
        rows = result.all()

        # Aggregate by user: total points and class with max points for display
        by_user: Dict[UUID, Dict[str, Any]] = defaultdict(
            lambda: {"total": Decimal("0"), "class_id": None, "class_name": "", "name": ""}
        )
        for r in rows:
            uid = r.user_id
            pts = r.points or Decimal("0")
            by_user[uid]["total"] += pts
            by_user[uid]["name"] = f"{r.first_name or ''} {r.last_name or ''}".strip()
            if by_user[uid]["class_id"] is None or pts > (by_user[uid].get("class_pts") or 0):
                by_user[uid]["class_id"] = r.class_id
                cn = (r.class_name or "").strip()
                sc = (r.sub_class or "").strip()
                by_user[uid]["class_name"] = f"{cn} - {sc}" if sc else (cn or "")
                by_user[uid]["class_pts"] = pts

        sorted_students = sorted(
            ({"user_id": uid, **v} for uid, v in by_user.items() if v["total"] > 0),
            key=lambda x: x["total"],
            reverse=True,
        )[:10]
        top_students = [
            LeaderboardStudentEntry(
                rank=i + 1,
                student_id=s["user_id"],
                student_name=(s.get("name") or "").strip(),
                class_id=s["class_id"],
                class_name=(s.get("class_name") or "").strip(),
                points=float(s["total"]),
            )
            for i, s in enumerate(sorted_students)
        ]

        # Top classes: sum of arena performer points per class
        class_where = [Class.school_id == school_id, arena_filter]
        if class_ids is not None:
            class_where.append(Class.id.in_(class_ids))
        class_pts = (
            select(
                Class.id.label("class_id"),
                Class.name.label("class_name"),
                Class.sub_class,
                func.coalesce(func.sum(ArenaPerformer.total_points), 0).label("score"),
            )
            .select_from(Class)
            .join(Arena, Arena.class_id == Class.id)
            .join(ArenaPerformer, ArenaPerformer.arena_id == Arena.id)
            .where(and_(*class_where))
            .group_by(Class.id, Class.name, Class.sub_class)
        )
        result_classes = await db.execute(class_pts)
        class_rows = result_classes.all()
        sorted_classes = sorted(
            [
                {
                    "class_id": r.class_id,
                    "class_name": (
                        f"{r.class_name or ''} - {r.sub_class or ''}".strip()
                        if r.sub_class else (r.class_name or "").strip()
                    ),
                    "score": float(r.score or 0),
                }
                for r in class_rows
                if (r.score or 0) > 0
            ],
            key=lambda x: x["score"],
            reverse=True,
        )[:10]
        top_classes = [
            LeaderboardClassEntry(rank=i + 1, class_id=c["class_id"], class_name=c["class_name"], score=c["score"])
            for i, c in enumerate(sorted_classes)
        ]

        return LeaderboardResponse(
            top_students=top_students,
            top_classes=top_classes,
            timeframe=timeframe,
        )

    @staticmethod
    async def create_language(db: AsyncSession, name: str, code: str) -> Optional[Language]:
        """
        Create a new global language.
        Returns None if a language with the same name or code already exists.
        """
        # Check for duplicate name or code
        existing_stmt = select(Language).where(
            (Language.name == name) | (Language.code == code)
        )
        result = await db.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return None

        # Create new language
        language = Language(
            name=name,
            code=code,
            is_active=True
        )
        db.add(language)
        await db.flush()
        await db.refresh(language)
        return language

    @staticmethod
    async def delete_language(db: AsyncSession, language_id: int) -> Dict[str, Any]:
        """
        Soft delete a language (set is_active=False).
        Returns dict with:
        - 'found': bool - whether language exists
        - 'in_use': bool - whether language is in use
        - 'schools_count': int - number of schools using it
        - 'classes_count': int - number of classes using it
        - 'classrooms_count': int - number of classrooms using it
        """
        # Check if language exists
        lang_stmt = select(Language).where(Language.id == language_id)
        result = await db.execute(lang_stmt)
        language = result.scalar_one_or_none()

        if not language:
            return {"found": False}

        # Check usage in school_languages junction table
        schools_count_stmt = select(func.count()).select_from(school_languages).where(
            school_languages.c.language_id == language_id
        )
        schools_count = await db.scalar(schools_count_stmt) or 0

        # Check usage in classes table
        classes_count_stmt = select(func.count()).select_from(Class).where(
            Class.language_id == language_id
        )
        classes_count = await db.scalar(classes_count_stmt) or 0

        # Check usage in classrooms table
        classrooms_count_stmt = select(func.count()).select_from(Classroom).where(
            Classroom.language_id == language_id
        )
        classrooms_count = await db.scalar(classrooms_count_stmt) or 0

        total_usage = schools_count + classes_count + classrooms_count

        if total_usage > 0:
            return {
                "found": True,
                "in_use": True,
                "schools_count": schools_count,
                "classes_count": classes_count,
                "classrooms_count": classrooms_count
            }

        # No usage, safe to soft delete
        language.is_active = False
        await db.flush()

        return {
            "found": True,
            "in_use": False,
            "schools_count": 0,
            "classes_count": 0,
            "classrooms_count": 0
        }
