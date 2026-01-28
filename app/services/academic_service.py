from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, ClassSchedule, Semester, class_enrollments, teacher_assignments
from app.models.enums import StudentRole, ClassStatus
from app.schemas.academic import ClassCreate, ClassUpdate, ScheduleBase

class AcademicService:
    @staticmethod
    async def get_class_by_id(db: AsyncSession, class_id: UUID) -> Optional[Class]:
        result = await db.execute(
            select(Class)
            .options(selectinload(Class.schedules))
            .where(Class.id == class_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_class(
        db: AsyncSession,
        school_id: UUID,
        class_data: ClassCreate
    ) -> Class:
        # Create Class
        new_class = Class(
            school_id=school_id,
            semester_id=class_data.semester_id,
            language_id=class_data.language_id,
            name=class_data.name,
            sub_class=class_data.sub_class,
            description=class_data.description,
            status=ClassStatus.ACTIVE
        )
        db.add(new_class)
        await db.flush()
        
        # Add Schedules
        for sched in class_data.schedule:
            schedule = ClassSchedule(
                class_id=new_class.id,
                day_of_week=sched.day_of_week,
                start_time=sched.start_time,
                end_time=sched.end_time
            )
            db.add(schedule)
            
        await db.commit()
        await db.commit()
        
        # Fetch with eager load to ensure relationships are available for Pydantic
        stmt = select(Class).options(selectinload(Class.schedules)).where(Class.id == new_class.id)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def get_teacher_classes(db: AsyncSession, teacher_id: UUID) -> List[Class]:
        """Get all classes assigned to a teacher"""
        # Join through teacher_assignments table
        stmt = (
            select(Class)
            .join(teacher_assignments, teacher_assignments.c.class_id == Class.id)
            .where(teacher_assignments.c.teacher_id == teacher_id)
            .options(selectinload(Class.schedules))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def add_student_to_class(
        db: AsyncSession,
        class_id: UUID,
        student_id: UUID,
        role: StudentRole = StudentRole.STUDENT
    ) -> bool:
        """Add student to class roster"""
        # Check if already enrolled
        stmt = select(class_enrollments).where(
            and_(
                class_enrollments.c.class_id == class_id,
                class_enrollments.c.student_id == student_id
            )
        )
        result = await db.execute(stmt)
        if result.first():
            return False # Already enrolled
            
        # Insert
        stmt = insert(class_enrollments).values(
            class_id=class_id,
            student_id=student_id,
            role=role,
            joined_at=datetime.utcnow()
        )
        await db.execute(stmt)
        await db.commit()
        return True

    @staticmethod
    async def remove_student_from_class(
        db: AsyncSession,
        class_id: UUID,
        student_id: UUID
    ) -> bool:
        """Remove student from class roster"""
        stmt = delete(class_enrollments).where(
            and_(
                class_enrollments.c.class_id == class_id,
                class_enrollments.c.student_id == student_id
            )
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount > 0

    @staticmethod
    async def get_class_roster(db: AsyncSession, class_id: UUID) -> List[Dict]:
        """Get students in a class with their roles"""
        # This requires a join to get user details
        from app.models.user import User
        
        stmt = (
            select(User, class_enrollments.c.role, class_enrollments.c.joined_at)
            .join(class_enrollments, class_enrollments.c.student_id == User.id)
            .where(class_enrollments.c.class_id == class_id)
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        # Format as list of dicts or custom objects
        roster = []
        for user, role, joined in rows:
            user_dict = {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "role": role,
                "joined_at": joined,
                "profile_picture_url": user.profile_picture_url
            }
            roster.append(user_dict)
            
        return roster
