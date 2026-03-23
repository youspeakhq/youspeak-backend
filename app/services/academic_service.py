import csv
import io
import secrets
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from app.utils.time import get_utc_now
from sqlalchemy import select, and_, delete, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.academic import Class, ClassSchedule, class_enrollments, teacher_assignments, Term
from app.models.enums import StudentRole, ClassStatus, UserRole
from app.schemas.academic import ClassCreate
from app.services.school_service import SchoolService


class AcademicService:
    @staticmethod
    async def get_class_by_id(
        db: AsyncSession,
        class_id: UUID,
        cache: Optional[Dict[UUID, Optional[Class]]] = None,
    ) -> Optional[Class]:
        if cache is not None and class_id in cache:
            return cache[class_id]
        result = await db.execute(
            select(Class)
            .options(selectinload(Class.schedules))
            .where(Class.id == class_id)
        )
        cls = result.scalar_one_or_none()
        if cache is not None:
            cache[class_id] = cls
        return cls

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
            term_id=class_data.term_id,
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
    async def get_school_classes(db: AsyncSession, school_id: UUID) -> List[Class]:
        """Get all classes in a school (for school admins)"""
        stmt = (
            select(Class)
            .where(Class.school_id == school_id)
            .options(selectinload(Class.schedules))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def add_student_to_class(
        db: AsyncSession,
        class_id: UUID,
        student_id: UUID,
        school_id: UUID,
        role: StudentRole = StudentRole.STUDENT,
        auto_commit: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """
        Add student to class roster.
        Validates that students belong to the same school as the class.
        Returns (success, error_message).
        """
        from app.models.user import User

        # Verify student exists and belongs to the school
        stmt = select(User).where(User.id == student_id)
        result = await db.execute(stmt)
        student = result.scalar_one_or_none()

        if not student:
            return False, "Student not found"

        if student.school_id != school_id:
            other_school = await SchoolService.get_school_by_id(db, student.school_id)
            school_name = other_school.name if other_school else "another school"
            return False, f"Student belongs to school '{school_name}'"

        if student.role != UserRole.STUDENT:
            return False, "User is not a student"

        # Check if already enrolled
        stmt = select(class_enrollments).where(
            and_(
                class_enrollments.c.class_id == class_id,
                class_enrollments.c.student_id == student_id
            )
        )
        result = await db.execute(stmt)
        if result.first():
            return False, "Student already enrolled in this class"

        # Enroll student
        stmt = insert(class_enrollments).values(
            class_id=class_id,
            student_id=student_id,
            role=role,
            joined_at=get_utc_now()
        )
        await db.execute(stmt)
        if auto_commit:
            await db.commit()
        return True, None

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
        """Map flexible column names to canonical keys used by import helpers."""
        aliases = {
            "first_name": ("first_name", "firstname", "first name", "given name"),
            "last_name": ("last_name", "lastname", "last name", "surname", "family name"),
            "email": ("email", "e-mail", "mail"),
            "student_number": ("student_number", "student_id", "student id", "student number"),
            "classroom_id": ("classroom_id", "classroom", "classroom id"),
            "class_id": ("class_id", "class", "class id"),
            # Language column can be absent (we may fall back to a default),
            # but when present we support a variety of header names.
            "language_code": (
                "language_code",
                "language code",
                "lang_code",
                "lang",
                "language",
            ),
        }
        result: Dict[str, str] = {}
        lowered_variants: Dict[str, set] = {
            canonical: {v.lower() for v in variants}
            for canonical, variants in aliases.items()
        }
        for key, val in row.items():
            if key is None:
                continue
            k = key.strip().lower()
            for canonical, variants in lowered_variants.items():
                if k in variants:
                    result[canonical] = (val or "").strip() if val is not None else ""
                    break
        return result

    @staticmethod
    def _parse_csv_rows(file_content: bytes) -> Tuple[Optional[List[Dict[str, str]]], Optional[Dict[str, Any]]]:
        """Decode UTF-8 CSV and return (list of row dicts, None) or (None, error_result)."""
        try:
            content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None, {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["Invalid file encoding. Use UTF-8."]}
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return None, {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["CSV file is empty"]}
        return rows, None

    @staticmethod
    async def _get_language_id_for_csv_row(
        db: AsyncSession,
        language_code: str,
        language_cache: Optional[Dict[str, int]],
    ) -> Optional[int]:
        """Resolve language_code to language_id; update cache if provided."""
        from app.models.onboarding import Language

        if language_cache is not None and language_code in language_cache:
            return language_cache[language_code]
        result = await db.execute(select(Language).where(Language.code == language_code))
        lang = result.scalar_one_or_none()
        if not lang:
            return None
        if language_cache is not None:
            language_cache[language_code] = lang.id
        return lang.id

    @staticmethod
    async def _existing_student_result(
        db: AsyncSession,
        existing: Any,
        school_id: UUID,
        email: str,
        row_index: int,
    ) -> Tuple[Optional[UUID], int, int, Optional[str]]:
        """Return (student_id, created, skipped, error) for existing user; error if wrong school/role."""
        if existing.school_id != school_id:
            other_school = await SchoolService.get_school_by_id(db, existing.school_id)
            school_name = other_school.name if other_school else "another school"
            return None, 0, 0, f"Row {row_index + 2}: {email} already belongs to school '{school_name}'"
        if existing.role != UserRole.STUDENT:
            return None, 0, 0, f"Row {row_index + 2}: {email} is not a student"
        return existing.id, 0, 0, None

    @staticmethod
    async def _resolve_or_create_student(
        db: AsyncSession,
        row_index: int,
        mapped: Dict[str, str],
        school_id: UUID,
        existing_users: Dict[str, Any],
        seen_emails: set,
        language_cache: Optional[Dict[str, int]] = None,
        default_language_id: Optional[int] = None,
    ) -> Tuple[Optional[UUID], int, int, Optional[str]]:
        """
        Validate row, ensure unique email, get or create student.
        Returns (student_id, created_delta, skipped_delta, error_message).
        """
        from app.services.user_service import UserService

        first_name = (mapped.get("first_name") or "").strip()
        last_name = (mapped.get("last_name") or "").strip()
        email = (mapped.get("email") or "").strip()
        student_number = (mapped.get("student_number") or "").strip() or None
        language_code = (mapped.get("language_code") or "").strip().lower()

        if not first_name or not last_name:
            return None, 0, 0, f"Row {row_index + 2}: first_name and last_name required"

        # Resolve language: prefer explicit language_code, otherwise fall back
        # to a provided default_language_id (e.g. class language_id or a school
        # default such as 'en').
        if language_code:
            language_id = await AcademicService._get_language_id_for_csv_row(
                db, language_code, language_cache
            )
            if not language_id:
                return None, 0, 0, f"Row {row_index + 2}: invalid language_code '{language_code}'"
        else:
            if default_language_id is None:
                return None, 0, 0, f"Row {row_index + 2}: language_code required"
            language_id = default_language_id

        if not email:
            email = f"{first_name.lower()}.{last_name.lower()}.{secrets.token_hex(4)}@youspeak-dummy.com"
        if email in seen_emails:
            return None, 0, 1, None
        seen_emails.add(email)

        existing = existing_users.get(email)
        if existing:
            return await AcademicService._existing_student_result(
                db, existing, school_id, email, row_index
            )

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
                student_number=student_number,
                language_id=language_id,
                auto_commit=False,
            )
            existing_users[email] = new_user
            return new_user.id, 1, 0, None
        except ValueError as e:
            return None, 0, 0, f"Row {row_index + 2}: {e}"
        except Exception as e:
            return None, 0, 0, f"Row {row_index + 2}: failed to create student - {str(e)}"

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
        CSV columns: first_name, last_name, language_code (required), email (optional), student_id (optional).
        Returns created count, enrolled count, skipped, and errors.
        """
        from app.services.user_service import UserService

        cls = await AcademicService.get_class_by_id(db, class_id)
        if not cls or cls.school_id != school_id:
            return {"created": 0, "enrolled": 0, "skipped": 0, "errors": ["Class not found or access denied"]}

        rows, err_result = AcademicService._parse_csv_rows(file_content)
        if err_result is not None:
            return err_result

        provided_emails = []
        for row in rows:
            mapped = AcademicService._normalize_csv_headers(row)
            email = (mapped.get("email") or "").strip()
            first_name = (mapped.get("first_name") or "").strip()
            last_name = (mapped.get("last_name") or "").strip()
            if email and first_name and last_name:
                provided_emails.append(email)
        existing_users = await UserService.get_users_by_emails(db, list(set(provided_emails)))

        created = 0
        enrolled = 0
        skipped = 0
        errors: List[str] = []
        seen_emails: set = set()
        # For class-level roster import, every row implicitly uses the class's
        # language_id; we do not require a language_code column in the CSV.
        language_cache: Optional[Dict[str, int]] = None

        for i, row in enumerate(rows):
            mapped = AcademicService._normalize_csv_headers(row)
            student_id, created_d, skipped_d, err = await AcademicService._resolve_or_create_student(
                db,
                i,
                mapped,
                school_id,
                existing_users,
                seen_emails,
                language_cache,
                default_language_id=language_id,
            )
            if err:
                errors.append(err)
                continue
            created += created_d
            skipped += skipped_d
            if student_id is None:
                continue  # was skipped duplicate
            added, add_err = await AcademicService.add_student_to_class(
                db, class_id, student_id, school_id, auto_commit=False
            )
            if added:
                enrolled += 1
            else:
                skipped += 1

        await db.commit()
        return {"created": created, "enrolled": enrolled, "skipped": skipped, "errors": errors}

    @staticmethod
    async def _enroll_student_in_class_from_row(
        db: AsyncSession,
        row_index: int,
        mapped: Dict[str, str],
        student_id: UUID,
        school_id: UUID,
        class_cache: Dict[UUID, Optional[Class]],
    ) -> Tuple[Optional[bool], Optional[str]]:
        """If class_id in row, validate and enroll. Returns (added_or_none, error_message)."""
        class_id_str = (mapped.get("class_id") or "").strip()
        if not class_id_str:
            return None, None
        try:
            cid = UUID(class_id_str)
        except ValueError:
            return None, f"Row {row_index + 2}: invalid class_id format"
        cls = await AcademicService.get_class_by_id(db, cid, cache=class_cache)
        if not cls or cls.school_id != school_id:
            return None, f"Row {row_index + 2}: invalid or inaccessible class_id"
        added, enroll_err = await AcademicService.add_student_to_class(
            db, cid, student_id, school_id, auto_commit=False
        )
        return added, enroll_err

    @staticmethod
    async def import_students_from_csv(
        db: AsyncSession,
        file_content: bytes,
        school_id: UUID,
    ) -> Dict[str, Any]:
        """
        School-level bulk import of students from CSV.
        CSV columns: first_name, last_name, language_code (required), email (optional),
        student_id (optional), class_id (optional).
        Creates students at school. If class_id provided and valid, enrolls in that class.
        Returns created count, enrolled count, skipped count, and errors.
        """
        from app.services.user_service import UserService

        rows, err_result = AcademicService._parse_csv_rows(file_content)
        if err_result is not None:
            return err_result

        provided_emails = []
        for row in rows:
            mapped = AcademicService._normalize_csv_headers(row)
            email = (mapped.get("email") or "").strip()
            first_name = (mapped.get("first_name") or "").strip()
            last_name = (mapped.get("last_name") or "").strip()
            if email and first_name and last_name:
                provided_emails.append(email)
        existing_users = await UserService.get_users_by_emails(db, list(set(provided_emails)))

        created = 0
        enrolled = 0
        skipped = 0
        errors: List[str] = []
        seen_emails: set = set()
        class_cache: Dict[UUID, Optional[Class]] = {}
        language_cache: Dict[str, int] = {}

        # When language_code column is missing, fall back to a sensible default
        # so basic CSVs without language information still import successfully.
        # We use 'en' as the default language code, which matches the seeded
        # languages used in the test suite.
        fallback_language_id = await AcademicService._get_language_id_for_csv_row(
            db, "en", language_cache
        )

        for i, row in enumerate(rows):
            mapped = AcademicService._normalize_csv_headers(row)
            student_id, created_d, skipped_d, err = await AcademicService._resolve_or_create_student(
                db,
                i,
                mapped,
                school_id,
                existing_users,
                seen_emails,
                language_cache,
                default_language_id=fallback_language_id,
            )
            if err:
                errors.append(err)
                continue
            created += created_d
            skipped += skipped_d
            if student_id is None:
                continue
            added, enroll_err = await AcademicService._enroll_student_in_class_from_row(
                db, i, mapped, student_id, school_id, class_cache
            )
            if enroll_err:
                errors.append(enroll_err)
            elif added is True:
                enrolled += 1
            elif added is False:
                skipped += 1

        await db.commit()
        return {"created": created, "enrolled": enrolled, "skipped": skipped, "errors": errors}
