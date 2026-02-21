"""User Service - Business Logic Layer"""

import csv
import io
import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.user import User
from app.models.enums import UserRole
from app.models.access_code import TeacherAccessCode
from app.models.student_trash import StudentTrash
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)

class UserService:
    """Service layer for user-related operations"""

    @staticmethod
    async def generate_next_student_number(db: AsyncSession, school_id: UUID) -> str:
        """Generate next student_number in format {year}-{seq} (e.g. 2025-001). Unique per school."""
        from sqlalchemy import cast, Integer

        year = datetime.utcnow().year
        prefix = f"{year}-"
        start_pos = len(prefix) + 1
        # Only consider student_numbers matching {year}-{digits} (ignore custom formats like 2025-abc)
        pattern = f"^{year}-\\d+$"
        result = await db.execute(
            select(func.max(cast(
                func.substring(User.student_number, start_pos),
                Integer
            ))).where(
                User.school_id == school_id,
                User.student_number.isnot(None),
                User.student_number.op("~")(pattern),
            )
        )
        max_seq = result.scalar_one_or_none()
        next_seq = (max_seq or 0) + 1
        return f"{year}-{next_seq:03d}"

    @staticmethod
    async def create_user(
        db: AsyncSession,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        school_id: UUID,
        role: UserRole = UserRole.STUDENT,
        is_active: bool = True,
        student_number: Optional[str] = None,
        auto_commit: bool = True,
    ) -> User:
        """
        Create a new user. For students, auto-generates student_number as {year}-{seq} if not provided.
        When auto_commit=False, uses flush instead of commit (for batch imports).
        """
        if role == UserRole.STUDENT:
            if student_number is None:
                student_number = await UserService.generate_next_student_number(db, school_id)
            else:
                existing = await UserService.get_user_by_student_number(db, school_id, student_number)
                if existing:
                    raise ValueError(f"Student number {student_number} already exists for this school")

        hashed_password = get_password_hash(password)

        db_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_password,
            school_id=school_id,
            role=role,
            is_active=is_active,
            student_number=student_number if role == UserRole.STUDENT else None,
        )

        db.add(db_user)
        if auto_commit:
            await db.commit()
            await db.refresh(db_user)
        else:
            await db.flush()
            await db.refresh(db_user)
        return db_user
    
    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
        """
        Get user by email.
        
        Args:
            db: Database session
            email: User email
            
        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_existing_emails(db: AsyncSession, emails: List[str]) -> set:
        """Return set of emails that already exist in users table. One query for bulk check."""
        if not emails:
            return set()
        result = await db.execute(select(User.email).where(User.email.in_(emails)))
        return {row[0] for row in result.all()}

    @staticmethod
    async def get_users_by_emails(db: AsyncSession, emails: List[str]) -> Dict[str, User]:
        """Return dict of email -> User for existing users. One query for bulk lookup."""
        if not emails:
            return {}
        result = await db.execute(select(User).where(User.email.in_(emails)))
        return {u.email: u for u in result.scalars().all()}

    @staticmethod
    async def get_user_by_student_number(
        db: AsyncSession, school_id: UUID, student_number: str
    ) -> Optional[User]:
        """Get user by student_number within a school."""
        result = await db.execute(
            select(User).where(
                User.school_id == school_id,
                User.student_number == student_number,
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_users(
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[User], int]:
        """
        Get paginated list of users.
        
        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (users list, total count)
        """
        # Get total count
        count_result = await db.execute(select(func.count(User.id)))
        total = count_result.scalar_one()
        
        # Get users
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.enrolled_classrooms),
                selectinload(User.taught_classrooms)
            )
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        return list(users), total
    
    @staticmethod
    async def update_user(
        db: AsyncSession,
        user_id: UUID,
        user_update: UserUpdate
    ) -> Optional[User]:
        """
        Update user information.
        
        Args:
            db: Database session
            user_id: User ID
            user_update: Updated user data
            
        Returns:
            Updated user or None if not found
        """
        db_user = await UserService.get_user_by_id(db, user_id)
        if not db_user:
            return None
        
        # Update fields
        update_data = user_update.model_dump(exclude_unset=True)
        
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
        
        for field, value in update_data.items():
            setattr(db_user, field, value)
        
        await db.commit()
        await db.refresh(db_user)
        
        return db_user
    
    @staticmethod
    async def delete_user(db: AsyncSession, user_id: UUID) -> bool:
        """
        Delete user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if deleted, False if not found
        """
        db_user = await UserService.get_user_by_id(db, user_id)
        if not db_user:
            return False
        
        await db.delete(db_user)
        await db.commit()
        
        return True
    
    @staticmethod
    async def authenticate_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user with email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            User if authenticated, None otherwise
        """
        user = await UserService.get_user_by_email(db, email)
        
        if not user:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        if not user.is_active:
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()
        
        return user
    
    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: UUID,
        current_password: str,
        new_password: str
    ) -> Optional[User]:
        """
        Change user password.
        
        Args:
            db: Database session
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            Updated user or None if authentication failed
        """
        user = await UserService.get_user_by_id(db, user_id)
        
        if not user:
            return None
        
        if not verify_password(current_password, user.hashed_password):
            return None
        
        user.hashed_password = get_password_hash(new_password)
        await db.commit()
        await db.refresh(user)
        
        return user
    
    # YouSpeak-specific methods
    
    @staticmethod
    async def verify_access_code(db: AsyncSession, code: str) -> Optional[UUID]:
        """
        Verify teacher access code and return school_id if valid.
        """
        result = await db.execute(
            select(TeacherAccessCode).where(
                TeacherAccessCode.code == code,
                TeacherAccessCode.is_used == False,
                or_(
                    TeacherAccessCode.expires_at.is_(None),
                    TeacherAccessCode.expires_at > datetime.utcnow()
                )
            )
        )
        access_code = result.scalar_one_or_none()
        return access_code.school_id if access_code else None
    
    @staticmethod
    async def create_invited_teacher(
        db: AsyncSession,
        email: str,
        first_name: str,
        last_name: str,
        school_id: UUID,
        placeholder_password: str,
    ) -> User:
        """Create teacher with is_active=False. Used when admin invites; teacher activates via code."""
        hashed = get_password_hash(placeholder_password)
        teacher = User(
            email=email,
            hashed_password=hashed,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=False,
        )
        db.add(teacher)
        await db.flush()
        return teacher

    @staticmethod
    async def get_access_code_by_code(db: AsyncSession, code: str) -> Optional[TeacherAccessCode]:
        """Get access code by code string if valid (not used, not expired)."""
        result = await db.execute(
            select(TeacherAccessCode).where(
                TeacherAccessCode.code == code,
                TeacherAccessCode.is_used == False,
                or_(
                    TeacherAccessCode.expires_at.is_(None),
                    TeacherAccessCode.expires_at > datetime.utcnow()
                )
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_teacher_with_code(
        db: AsyncSession,
        code: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str
    ) -> Optional[User]:
        """
        Activate teacher using access code.
        If invited_teacher_id is set: update existing teacher (password, is_active=True).
        Else (legacy): create new teacher.
        """
        access_code = await UserService.get_access_code_by_code(db, code)
        if not access_code:
            return None

        if access_code.invited_teacher_id:
            teacher = await db.get(User, access_code.invited_teacher_id)
            if not teacher or teacher.role != UserRole.TEACHER:
                return None
            if teacher.email != email:
                return None
            teacher.hashed_password = get_password_hash(password)
            teacher.is_active = True
            access_code.is_used = True
            access_code.used_by_teacher_id = teacher.id
            await db.commit()
            await db.refresh(teacher)
            return teacher

        school_id = access_code.school_id
        existing = await UserService.get_user_by_email(db, email)
        if existing:
            return None
        hashed_password = get_password_hash(password)
        teacher = User(
            email=email,
            hashed_password=hashed_password,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.TEACHER,
            school_id=school_id,
            is_active=True
        )
        db.add(teacher)
        await db.flush()
        access_code.is_used = True
        access_code.used_by_teacher_id = teacher.id
        await db.commit()
        await db.refresh(teacher)
        return teacher

    @staticmethod
    async def import_teachers_from_csv(
        db: AsyncSession,
        file_content: bytes,
        school_id: UUID,
        admin_id: UUID,
    ) -> Dict[str, Any]:
        """
        Bulk import teachers from CSV.
        CSV columns: first_name, last_name, email, classroom_id (optional).
        Creates invited teachers (is_active=False) with access codes.
        Returns created count, skipped count, errors, and invitations (email, first_name, code) for sending.
        """
        from app.core import security
        from app.services.academic_service import AcademicService
        from app.services.classroom_service import ClassroomService

        created = 0
        skipped = 0
        errors: List[str] = []
        invitations: List[Dict[str, str]] = []
        seen_emails: set = set()
        classroom_cache: Dict[UUID, Any] = {}

        try:
            content = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            return {"created": 0, "skipped": 0, "errors": ["Invalid file encoding. Use UTF-8."], "invitations": []}

        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            return {"created": 0, "skipped": 0, "errors": ["CSV file is empty"], "invitations": []}

        emails_to_check = []
        for row in rows:
            mapped = AcademicService._normalize_csv_headers(row)
            first_name = (mapped.get("first_name") or "").strip()
            last_name = (mapped.get("last_name") or "").strip()
            email = (mapped.get("email") or "").strip()
            if first_name and last_name and email:
                emails_to_check.append(email)

        existing_emails = await UserService.get_existing_emails(db, list(set(emails_to_check)))

        for i, row in enumerate(rows):
            mapped = AcademicService._normalize_csv_headers(row)
            first_name = (mapped.get("first_name") or "").strip()
            last_name = (mapped.get("last_name") or "").strip()
            email = (mapped.get("email") or "").strip()

            if not first_name or not last_name:
                errors.append(f"Row {i + 2}: first_name and last_name required")
                continue
            if not email:
                errors.append(f"Row {i + 2}: email required")
                continue

            if email in seen_emails:
                skipped += 1
                continue
            seen_emails.add(email)

            if email in existing_emails:
                errors.append(f"Row {i + 2}: {email} already exists")
                continue

            classroom_id_str = (mapped.get("classroom_id") or "").strip()
            classroom_id: Optional[UUID] = None
            if classroom_id_str:
                try:
                    classroom_id = UUID(classroom_id_str)
                except ValueError:
                    errors.append(f"Row {i + 2}: invalid classroom_id")
                    continue

            placeholder = secrets.token_hex(32)
            teacher = await UserService.create_invited_teacher(
                db=db,
                email=email,
                first_name=first_name,
                last_name=last_name,
                school_id=school_id,
                placeholder_password=placeholder,
            )
            existing_emails.add(email)

            code = security.generate_access_code()
            access_code = TeacherAccessCode(
                code=code,
                school_id=school_id,
                created_by_admin_id=admin_id,
                invited_teacher_id=teacher.id,
                expires_at=datetime.utcnow() + timedelta(days=7),
                is_used=False,
            )
            db.add(access_code)

            if classroom_id:
                await ClassroomService.add_teacher_to_classroom(
                    db, classroom_id, teacher.id, school_id,
                    auto_commit=False,
                    classroom_cache=classroom_cache,
                    skip_user_validation=True,
                )

            created += 1
            invitations.append({"email": email, "first_name": first_name, "code": code})

        await db.commit()
        return {"created": created, "skipped": skipped, "errors": errors, "invitations": invitations}

    @staticmethod
    async def get_users_by_school_and_role(
        db: AsyncSession,
        school_id: UUID,
        role: Optional[UserRole] = None,
        status: str = "active"
    ) -> List[User]:
        """Get users by school and role, filtering by status (active or deleted)"""
        if role == UserRole.TEACHER:
            query = (
                select(User)
                .where(User.school_id == school_id)
                .options(selectinload(User.taught_classrooms))
            )
        else:
            query = (
                select(User)
                .where(User.school_id == school_id)
                .options(selectinload(User.enrolled_classrooms))
            )

        if role:
            query = query.where(User.role == role)

        if status == "deleted":
            query = query.where(User.deleted_at.isnot(None))
        else:
            query = query.where(User.deleted_at.is_(None))

        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def soft_delete_user(db: AsyncSession, user_id: UUID) -> bool:
        """Soft delete user and move to trash if student"""
        result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
        user = result.scalar_one_or_none()
        if not user:
            return False
        
        user.soft_delete()
        
        # If user is a student, create a trash record
        if user.role == UserRole.STUDENT:
            trash = StudentTrash(user_id=user_id)
            db.add(trash)
            
        await db.commit()
        return True
    
    @staticmethod
    async def restore_user(db: AsyncSession, user_id: UUID) -> bool:
        """Restore soft-deleted user and remove from trash"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_deleted:
            return False
        
        user.restore()
        
        # Remove trash record if it exists
        trash_result = await db.execute(select(StudentTrash).where(StudentTrash.user_id == user_id))
        trash = trash_result.scalar_one_or_none()
        if trash:
            await db.delete(trash)
            
        await db.commit()
        return True

    @staticmethod
    async def cleanup_expired_trash(db: AsyncSession) -> int:
        """Permanently delete users whose trash retention has expired"""
        now = datetime.utcnow()
        expired_result = await db.execute(
            select(StudentTrash).where(StudentTrash.expires_at <= now)
        )
        expired_records = expired_result.scalars().all()
        
        count = 0
        for record in expired_records:
            # Permanently delete the user (CASCADE will handle the trash record)
            user = await db.get(User, record.user_id)
            if user:
                await db.delete(user)
                count += 1
        
        if count > 0:
            await db.commit()
            
        return count
