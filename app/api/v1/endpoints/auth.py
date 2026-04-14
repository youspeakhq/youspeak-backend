from datetime import timedelta
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core import security
from app.config import settings
from app.services.user_service import UserService
from app.services.school_service import SchoolService
from app.schemas.auth import (
    LoginRequest, Token, RegisterSchoolRequest, RegisterTeacherRequest,
    VerifyCodeRequest, PasswordResetRequest, PasswordResetEmailRequest,
    RefreshTokenRequest,
)
from app.schemas.school import SchoolCreate, ContactInquiryCreate
from app.models.enums import SchoolType, ProgramType
from app.models.onboarding import ContactInquiry
from app.schemas.responses import SuccessResponse
from app.services.email_service import send_password_reset
from app.core.logging import get_logger

router = APIRouter()


@router.post("/contact-inquiry", response_model=SuccessResponse[dict])
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


def _set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    """Set refresh token as HttpOnly cookie on the response."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,  # days -> seconds
        path="/api/v1/auth",  # only sent to auth endpoints
        domain=None,  # auto-detect from request
        secure=settings.is_production,  # HTTPS only in production
        httponly=True,  # not accessible via JS
        samesite="lax",  # CSRF protection
    )


@router.post("/login", response_model=SuccessResponse[Token])
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Unified login for all users.
    Returns JWT access token, refresh token, and user role.
    Also sets refresh token as HttpOnly cookie.
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

    data = SuccessResponse(
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

    response = JSONResponse(content=data.model_dump())
    _set_refresh_cookie(response, refresh_token)
    return response


@router.post("/refresh-token")
async def refresh_token(
    body: RefreshTokenRequest = None,
    refresh_token_cookie: str = Cookie(None, alias="refresh_token"),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Refresh access token using refresh token.

    Accepts refresh token from:
    1. HttpOnly cookie (preferred, XSS-safe)
    2. Request body (backward compatible with existing frontend)

    Returns new access + refresh token pair (token rotation).
    """
    log = get_logger(__name__)

    # Get refresh token: cookie takes precedence over body
    token = refresh_token_cookie
    if not token and body and body.refresh_token:
        token = body.refresh_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided",
        )

    # Decode and validate
    payload = security.decode_token(token)
    if not payload:
        log.warning("refresh_token_invalid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        log.warning("refresh_token_wrong_type", extra={"type": payload.get("type")})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists and is active
    from uuid import UUID
    user = await UserService.get_user_by_id(db, UUID(user_id))
    if not user or not user.is_active or user.is_deleted:
        log.warning("refresh_token_user_inactive", extra={"user_id": user_id})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or deleted",
        )

    # Issue new token pair (rotation)
    token_data = {"sub": str(user.id), "role": user.role}
    if user.school_id:
        token_data["school_id"] = str(user.school_id)

    new_access_token = security.create_access_token(data=token_data)
    new_refresh_token = security.create_refresh_token(
        data={"sub": str(user.id), "role": user.role}
    )

    log.info("token_refreshed", extra={"user_id": user_id})

    data = SuccessResponse(
        data=Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            role=user.role,
            user_id=str(user.id),
            school_id=str(user.school_id) if user.school_id else None,
        ),
        message="Token refreshed successfully",
    )

    response = JSONResponse(content=data.model_dump())
    _set_refresh_cookie(response, new_refresh_token)
    return response


@router.post("/logout")
async def logout() -> Any:
    """
    Clear the refresh token cookie.
    Frontend should also clear localStorage tokens.
    """
    response = JSONResponse(
        content=SuccessResponse(data={}, message="Logged out successfully").model_dump()
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth",
    )
    return response


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

    languages = school_in.languages or []
    return SuccessResponse(
        data={
            "school_id": str(school.id),
            "program_type": school.program_type.value,
            "languages": languages,
        },
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


@router.post("/password/request-reset", response_model=SuccessResponse)
async def request_password_reset(
    body: PasswordResetEmailRequest,
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Request a password reset. Sends an email with a reset link if the account exists.
    Always returns 200 to avoid email enumeration.
    """
    user = await UserService.get_user_by_email(db, email=body.email)
    if user:
        token = security.generate_password_reset_token(str(user.id))
        reset_link = f"{settings.FRONTEND_RESET_PASSWORD_URL.rstrip('/')}?token={quote(token, safe='')}"
        send_password_reset(body.email, reset_link)
    return SuccessResponse(
        data={},
        message="If an account exists with this email, you will receive a password reset link shortly."
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

    return SuccessResponse(data={}, message="Password updated successfully")
