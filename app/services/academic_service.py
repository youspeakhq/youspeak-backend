import csv
import io
import secrets
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, ClassSchedule, Semester, class_enrollments, teacher_assignments
from app.models.enums import StudentRole, ClassStatus, UserRole
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
        class_data: ClassCreate,
        teacher_id: UUID,
    ) -> Class:
        # Create Class
        new_class = Class(
            school_id=school_id,
            semester_id=class_data.semester_id,
            language_id=class_data.language_id,
            name=class_data.name,
            sub_class=class_data.sub_class,
            description=class_data.description,
            timeline=class_data.timeline,
            status=ClassStatus.ACTIVE,
            classroom_id=class_data.classroom_id,
        )
        db.add(new_class)
        await db.flush()

        # Assign creating teacher to the class
        stmt = insert(teacher_assignments).values(
            class_id=new_class.id,
            teacher_id=teacher_id,
            is_primary=True,
        )
        await db.execute(stmt)

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

        # Fetch with eager load to ensure relationships are available for Pydantic
        stmt = select(Class).options(selectinload(Class.schedules)).where(Class.id == new_class.id)
        result = await db.execute(stmt)
        return result.scalar_one()

    @staticmethod
    async def assign_teacher_to_classes(
        db: AsyncSession,
        teacher_id: UUID,
        class_ids: List[UUID],
        school_id: UUID,
    ) -> bool:
        """Assign teacher to classes. Validates all classes belong to school."""
        if not class_ids:
            return True
        stmt = select(Class).where(
            Class.id.in_(class_ids),
            Class.school_id == school_id,
        )
        result = await db.execute(stmt)
        valid_classes = result.scalars().all()
        if len(valid_classes) != len(class_ids):
            return False
        for cls in valid_classes:
            existing = await db.execute(
                select(teacher_assignments).where(
                    teacher_assignments.c.class_id == cls.id,
                    teacher_assignments.c.teacher_id == teacher_id,
                )
            )
            if existing.first():
                continue
            stmt = insert(teacher_assignments).values(
                class_id=cls.id,
                teacher_id=teacher_id,
                is_primary=False,
            )
            await db.execute(stmt)
        return True

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

    @staticmethod
    def _normalize_csv_headers(row: Dict[str, str]) -> Dict[str, str]:
        """Map flexible column names to canonical keys."""
        aliases = {
            "first_name": ("first_name", "firstname", "first name", "given name"),
            "last_name": ("last_name", "lastname", "last name", "surname", "family name"),
            "email": ("email", "e-mail", "mail"),
        }
        result = {}
        for canonical, variants in aliases.items():
            for key, val in row.items():
                if key.strip().lower() in [v.lower() for v in variants]:
                    result[canonical] = val.strip() if val else ""
                    break
        return result

    @staticmethod
    async def import_roster_from_csv(
        db: AsyncSession,
        class_id: UUID,
        file_content: bytes,
        school_id: UUID,
        language_id: int,
    ) -> Dict[str, Any]:
        """
        Bulk import students from CSV. Creates new students or enrolls existing ones.
        CSV columns: first_name, last_name, email (optional).
        Returns created count, enrolled count, skipped, and errors.
        """
        from app.models.user import User
        from app.services.user_service import UserService

        cls = await AcademicService.get_class_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            return {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["Class not found or access denied"]}

        created = 0
        enrolled = 0
        skipped = 0
        errors: List[str] = []
        seen_emails: set = set()

        try:
            content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["Invalid file encoding. Use UTF-8."]}

        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["CSV file is empty"]}

        for i, row in enumerate(rows):
            mapped = AcademicService._normalize_csv_headers(row)
            first_name = (mapped.get("first_name") or "").strip()
            last_name = (mapped.get("last_name") or "").strip()
            email = (mapped.get("email") or "").strip()

            if not first_name or not last_name:
                errors.append(f"Row {i + 2}: first_name and last_name required")
                continue

            if not email:
                email = f"{first_name.lower()}.{last_name.lower()}.{secrets.token_hex(4)}@youspeak-dummy.com"

            if email in seen_emails:
                skipped += 1
                continue
            seen_emails.add(email)

            existing = await UserService.get_user_by_email(db, email)
            if existing:
                if existing.school_id != school_id:
                    errors.append(f"Row {i + 2}: {email} belongs to another school")
                    continue
                if existing.role != UserRole.STUDENT:
                    errors.append(f"Row {i + 2}: {email} is not a student")
                    continue
                student_id = existing.id
            else:
                try:
                    new_user = await UserService.create_user(
                        db=db,
                        email=email,
                        password="Student123!",
                        first_name=first_name,
                        last_name=last_name,
                        school_id=school_id,
                        role=UserRole.STUDENT,
                        is_active=True,
                    )
                    student_id = new_user.id
                    created += 1
                except Exception as e:
                    errors.append(f"Row {i + 2}: failed to create student - {str(e)}")
                    continue

            added = await AcademicService.add_student_to_class(db, class_id, student_id)
            if added:
                enrolled += 1
            else:
                skipped += 1

        return {"created": created, "enrolled": enrolled, "skipped": skipped, "errors": errors}
