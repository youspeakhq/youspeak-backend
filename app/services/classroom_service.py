"""Classroom Service - Admin-created organizational units"""

from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from sqlalchemy import select, and_, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Classroom, classroom_teachers, classroom_students
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.academic import ClassroomCreate
from app.services.user_service import UserService
from app.services.school_service import SchoolService


class ClassroomService:
    @staticmethod
    async def create_classroom(
        db: AsyncSession,
        school_id: UUID,
        data: ClassroomCreate,
    ) -> Classroom:
        classroom = Classroom(
            school_id=school_id,
            name=data.name,
            language_id=data.language_id,
            level=data.level,
        )
        db.add(classroom)
        await db.commit()
        await db.refresh(classroom)
        return classroom

    @staticmethod
    async def get_classroom_by_id(
        db: AsyncSession,
        classroom_id: UUID,
        school_id: UUID,
        cache: Optional[Dict[UUID, Optional[Classroom]]] = None,
    ) -> Optional[Classroom]:
        if cache is not None and classroom_id in cache:
            return cache[classroom_id]
        result = await db.execute(
            select(Classroom)
            .where(
                Classroom.id == classroom_id,
                Classroom.school_id == school_id,
            )
        )
        classroom = result.scalar_one_or_none()
        if cache is not None:
            cache[classroom_id] = classroom
        return classroom

    @staticmethod
    async def list_classrooms(
        db: AsyncSession,
        school_id: UUID,
    ) -> List[Dict[str, Any]]:
        result = await db.execute(
            select(Classroom)
            .where(Classroom.school_id == school_id)
            .order_by(Classroom.name)
        )
        classrooms = result.scalars().all()
        out = []
        for c in classrooms:
            teacher_count = await db.scalar(
                select(func.count()).select_from(classroom_teachers).where(
                    classroom_teachers.c.classroom_id == c.id
                )
            )
            student_count = await db.scalar(
                select(func.count()).select_from(classroom_students).where(
                    classroom_students.c.classroom_id == c.id
                )
            )
            out.append({
                "id": c.id,
                "name": c.name,
                "language_id": c.language_id,
                "level": c.level.value,
                "school_id": c.school_id,
                "teacher_count": teacher_count or 0,
                "student_count": student_count or 0,
            })
        return out

    @staticmethod
    async def add_teacher_to_classroom(
        db: AsyncSession,
        classroom_id: UUID,
        teacher_id: UUID,
        school_id: UUID,
        auto_commit: bool = True,
        classroom_cache: Optional[Dict[UUID, Optional[Classroom]]] = None,
        skip_user_validation: bool = False,
    ) -> bool:
        classroom = await ClassroomService.get_classroom_by_id(
            db, classroom_id, school_id, cache=classroom_cache
        )
        if not classroom:
            return False
        if not skip_user_validation:
            user = await UserService.get_user_by_id(db, teacher_id)
            if not user or user.school_id != school_id or user.role != UserRole.TEACHER:
                return False
        existing = await db.execute(
            select(classroom_teachers).where(
                and_(
                    classroom_teachers.c.classroom_id == classroom_id,
                    classroom_teachers.c.teacher_id == teacher_id,
                )
            )
        )
        if existing.first():
            return False
        await db.execute(
            insert(classroom_teachers).values(
                classroom_id=classroom_id,
                teacher_id=teacher_id,
            )
        )
        if auto_commit:
            await db.commit()
        return True

    @staticmethod
    async def add_student_to_classroom(
        db: AsyncSession,
        classroom_id: UUID,
        student_id: UUID,
        school_id: UUID,
    ) -> Tuple[bool, Optional[str]]:
        """Returns (success, other_school_name). other_school_name is set when student belongs to another school."""
        classroom = await ClassroomService.get_classroom_by_id(db, classroom_id, school_id)
        if not classroom:
            return False, None
        user = await UserService.get_user_by_id(db, student_id)
        if not user:
            return False, None
        if user.role != UserRole.STUDENT:
            return False, None
        if user.school_id != school_id:
            other_school = await SchoolService.get_school_by_id(db, user.school_id)
            other_name = other_school.name if other_school else None
            return False, other_name
        existing = await db.execute(
            select(classroom_students).where(
                and_(
                    classroom_students.c.classroom_id == classroom_id,
                    classroom_students.c.student_id == student_id,
                )
            )
        )
        if existing.first():
            return False, None
        await db.execute(
            insert(classroom_students).values(
                classroom_id=classroom_id,
                student_id=student_id,
            )
        )
        await db.commit()
        return True, None

    @staticmethod
    async def teacher_teaches_classroom(
        db: AsyncSession,
        teacher_id: UUID,
        classroom_id: UUID,
    ) -> bool:
        """Check if a teacher teaches a specific classroom."""
        result = await db.execute(
            select(classroom_teachers).where(
                classroom_teachers.c.classroom_id == classroom_id,
                classroom_teachers.c.teacher_id == teacher_id,
            )
        )
        return result.first() is not None

    @staticmethod
    async def get_classroom_students(
        db: AsyncSession,
        classroom_id: UUID,
        school_id: UUID,
    ) -> List[User]:
        """Return students enrolled in the classroom. Empty list if classroom not found or not in school."""
        stmt = (
            select(Classroom)
            .options(selectinload(Classroom.students))
            .where(
                Classroom.id == classroom_id,
                Classroom.school_id == school_id,
            )
        )
        result = await db.execute(stmt)
        classroom = result.scalar_one_or_none()
        if not classroom:
            return []
        return list(classroom.students)

    @staticmethod
    async def get_classroom_teachers(
        db: AsyncSession,
        classroom_id: UUID,
        school_id: UUID,
    ) -> List[User]:
        """Return teachers assigned to the classroom. Empty list if classroom not found or not in school."""
        stmt = (
            select(Classroom)
            .options(selectinload(Classroom.teachers))
            .where(
                Classroom.id == classroom_id,
                Classroom.school_id == school_id,
            )
        )
        result = await db.execute(stmt)
        classroom = result.scalar_one_or_none()
        if not classroom:
            return []
        return list(classroom.teachers)
