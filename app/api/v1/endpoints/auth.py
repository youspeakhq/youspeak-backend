from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import security
from app.config import settings
from app.services.user_service import UserService
from app.services.school_service import SchoolService
from app.schemas.auth import (
    LoginRequest, Token, RegisterSchoolRequest, RegisterTeacherRequest,
    VerifyCodeRequest, PasswordResetRequest
)
from app.schemas.school import SchoolCreate, ContactInquiryCreate
from app.models.enums import SchoolType, ProgramType, UserRole
from app.models.onboarding import ContactInquiry
from app.schemas.responses import SuccessResponse, ErrorResponse

router = APIRouter()


@router.post("/contact-inquiry", response_model=SuccessResponse)
async def submit_contact_inquiry(
    inquiry_in: ContactInquiryCreate,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Pre-onboarding contact form (Tell us about your school).
    For demo requests, billing questions, new school onboarding inquiries.
    """
    inquiry = ContactInquiry(
        school_name=inquiry_in.school_name,
        email=inquiry_in.email,
        inquiry_type=inquiry_in.inquiry_type,
        message=inquiry_in.message,
    )
    db.add(inquiry)
    await db.commit()
    return SuccessResponse(
        data={"id": str(inquiry.id)},
        message="Inquiry submitted. We will review and contact you."
    )


@router.post("/login", response_model=SuccessResponse[Token])
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Unified login for all users.
    Returns JWT access token, refresh token, and user role.
    """
    user = await UserService.authenticate_user(db, email=login_data.email, password=login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_data = {"sub": str(user.id), "role": user.role}
    if user.school_id:
        token_data["school_id"] = str(user.school_id)
        
    access_token = security.create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )
    refresh_token = security.create_refresh_token(
        data={"sub": str(user.id), "role": user.role}
    )
    
    return SuccessResponse(
        data=Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            role=user.role,
            user_id=str(user.id),
            school_id=str(user.school_id) if user.school_id else None
        ),
        message="Login successful"
    )

@router.post("/register/school", response_model=SuccessResponse)
async def register_school(
    school_in: RegisterSchoolRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Register a new school tenant and its first admin user.
    """
    # Check if user email already exists
    user = await UserService.get_user_by_email(db, email=school_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )
    
    admin_data = {
        "email": school_in.email,
        "password": school_in.password,
        "first_name": "Admin",
        "last_name": "School",
    }
    
    school_data = SchoolCreate(
        name=school_in.school_name,
        school_type=school_in.school_type or SchoolType.SECONDARY,
        program_type=school_in.program_type or ProgramType.PARTNERSHIP,
        address_country=school_in.address_country,
        address_state=school_in.address_state,
        address_city=school_in.address_city,
        address_zip=school_in.address_zip,
    )
    
    school = await SchoolService.create_school_with_admin(
        db=db,
        school_data=school_data,
        admin_data=admin_data
    )
    
    if school_in.languages:
        await SchoolService.update_programs(db, school.id, school_in.languages)
    
    return SuccessResponse(
        data={"school_id": str(school.id)},
        message="School registered successfully"
    )

@router.post("/register/teacher", response_model=SuccessResponse)
async def register_teacher(
    teacher_in: RegisterTeacherRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Teacher Signup: Validates Access Code and creates account.
    """
    teacher = await UserService.create_teacher_with_code(
        db=db,
        code=teacher_in.access_code,
        email=teacher_in.email,
        password=teacher_in.password,
        first_name=teacher_in.first_name,
        last_name=teacher_in.last_name
    )
    
    if not teacher:
        # Check email for better error
        if await UserService.get_user_by_email(db, teacher_in.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=400, detail="Invalid or expired access code")
        
    return SuccessResponse(
        data={"user_id": str(teacher.id), "school_id": str(teacher.school_id)},
        message="Teacher account created successfully"
    )

@router.post("/verify-code", response_model=SuccessResponse)
async def verify_code(
    code_in: VerifyCodeRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Validate Teacher Access Code before form submit.
    """
    school_id = await UserService.verify_access_code(db, code_in.access_code)
    if not school_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired access code"
        )
    
    # Return school info
    school = await SchoolService.get_school_by_id(db, school_id)
    
    return SuccessResponse(
        data={
            "valid": True, 
            "school_name": school.name if school else "Unknown School"
        },
        message="Access code is valid"
    )

@router.post("/password/reset", response_model=SuccessResponse)
async def reset_password(
    reset_in: PasswordResetRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Complete password reset flow.
    """
    user_id_str = security.verify_password_reset_token(reset_in.token)
    if not user_id_str:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
        
    from uuid import UUID
    user_id = UUID(user_id_str)
    
    success = await UserService.update_password(db, user_id, reset_in.new_password)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
        
    return SuccessResponse(message="Password updated successfully")
