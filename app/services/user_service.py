"""User Service - Business Logic Layer"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.enums import UserRole
from app.models.access_code import TeacherAccessCode
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password


class UserService:
    """Service layer for user-related operations"""
    
    @staticmethod
    async def create_user(
        db: AsyncSession, 
        email: str, 
        password: str, 
        first_name: str, 
        last_name: str, 
        school_id: UUID,
        role: UserRole = UserRole.STUDENT,
        is_active: bool = True
    ) -> User:
        """
        Create a new user.
        """
        # Hash password
        hashed_password = get_password_hash(password)
        
        # Create user instance
        db_user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            hashed_password=hashed_password,
            school_id=school_id,
            role=role,
            is_active=is_active
        )
        
        db.add(db_user)
        await db.commit()
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
    async def create_teacher_with_code(
        db: AsyncSession,
        code: str,
        email: str,
        password: str,
        first_name: str,
        last_name: str
    ) -> Optional[User]:
        """Create teacher using access code"""
        # Verify code
        school_id = await UserService.verify_access_code(db, code)
        if not school_id:
            return None
        
        # Check email doesn't exist
        existing = await UserService.get_user_by_email(db, email)
        if existing:
            return None
        
        # Create teacher
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
        
        # Mark code as used
        result = await db.execute(select(TeacherAccessCode).where(TeacherAccessCode.code == code))
        access_code = result.scalar_one()
        access_code.is_used = True
        access_code.used_by_teacher_id = teacher.id
        
        await db.commit()
        await db.refresh(teacher)
        return teacher
    
    @staticmethod
    async def get_users_by_school_and_role(
        db: AsyncSession,
        school_id: UUID,
        role: Optional[UserRole] = None,
        include_deleted: bool = False
    ) -> List[User]:
        """Get users by school and role"""
        query = select(User).where(User.school_id == school_id)
        
        if role:
            query = query.where(User.role == role)
        
        if not include_deleted:
            query = query.where(User.deleted_at.is_(None))
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def soft_delete_user(db: AsyncSession, user_id: UUID) -> bool:
        """Soft delete user"""
        result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
        user = result.scalar_one_or_none()
        if not user:
            return False
        
        user.soft_delete()
        await db.commit()
        return True
    
    @staticmethod
    async def restore_user(db: AsyncSession, user_id: UUID) -> bool:
        """Restore soft-deleted user"""
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_deleted:
            return False
        
        user.restore()
        await db.commit()
        return True
