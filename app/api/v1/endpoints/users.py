"""User Management Endpoints"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
import math

from app.database import get_db
from app.schemas.user import User as UserSchema, UserUpdate, PasswordChange
from app.schemas.responses import PaginatedResponse
from app.services.user_service import UserService
from app.api.deps import get_current_user, require_admin
from app.models.user import User as UserModel
from app.models.enums import UserRole

router = APIRouter()


@router.get("", response_model=PaginatedResponse[UserSchema])
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_admin) # Only admin should list all generic users
) -> PaginatedResponse[UserSchema]:
    """
    Get paginated list of users.
    """
    skip = (page - 1) * page_size
    users, total = await UserService.get_users(db, skip=skip, limit=page_size)
    
    # Build response dicts while the DB session is still open so that
    # relationships are accessible without lazy loading.
    from app.schemas.academic import ClassroomBrief
    from app.schemas.user import UserResponse

    def _user_dict(u: UserModel) -> dict:
        # Combine classrooms from both relationships
        all_classrooms = []
        if u.role == UserRole.TEACHER:
            all_classrooms = [
                ClassroomBrief.model_validate(c)
                for c in (u.taught_classrooms or [])
            ]
        elif u.role == UserRole.STUDENT:
            all_classrooms = [
                ClassroomBrief.model_validate(c)
                for c in (u.enrolled_classrooms or [])
            ]
            
        return UserResponse(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            role=u.role,
            school_id=u.school_id,
            profile_picture_url=u.profile_picture_url,
            student_number=u.student_number if u.role == UserRole.STUDENT else None,
            is_verified=True if u.role != UserRole.STUDENT else False,
            created_at=u.created_at,
            updated_at=u.updated_at,
            last_login=getattr(u, "last_login", None),
            classrooms=all_classrooms,
        )

    serialized = [_user_dict(u) for u in users]
    total_pages = math.ceil(total / page_size)
    
    return PaginatedResponse(
        data=serialized,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    )


@router.get("/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
) -> UserSchema:
    """
    Get user by ID.
    """
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: UUID,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
) -> UserSchema:
    """
    Update user information.
    """
    # Users can only update their own profile unless they're an admin
    if current_user.id != user_id and current_user.role != UserRole.SCHOOL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    user = await UserService.update_user(db, user_id, user_update)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(require_admin)
) -> None:
    """
    Delete user (admin only).
    """
    success = await UserService.delete_user(db, user_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )


@router.post("/change-password", response_model=UserSchema)
async def change_password(
    password_change: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
) -> UserSchema:
    """
    Change user password.
    """
    user = await UserService.change_password(
        db,
        current_user.id,
        password_change.current_password,
        password_change.new_password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    return user
