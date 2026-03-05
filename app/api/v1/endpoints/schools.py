from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.services.school_service import SchoolService
from app.services.billing_service import BillingService
from app.services import storage_service as storage
from app.schemas.school import (
    SchoolResponse,
    SchoolUpdate,
    SchoolProgramsUpdate,
    SchoolProgramsResponse,
)
from app.schemas.billing import BillResponse
from app.schemas.responses import SuccessResponse, PaginatedResponse, PaginationMeta

router = APIRouter()


@router.get("/profile", response_model=SuccessResponse[SchoolResponse])
async def get_school_profile(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Fetch school details including languages offered. Admin only.
    Languages are updated via PUT /schools/program; this endpoint returns the current list.
    """
    school = await SchoolService.get_school_with_languages(db, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    return SuccessResponse(data=school)


@router.put("/profile", response_model=SuccessResponse[SchoolResponse])
async def update_school_profile(
    school_in: SchoolUpdate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Update bio-data. Admin only.
    """
    school = await SchoolService.update_school(
        db,
        current_user.school_id,
        school_in
    )
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school = await SchoolService.get_school_with_languages(db, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    return SuccessResponse(data=school, message="Profile updated successfully")


@router.put("/program", response_model=SuccessResponse[SchoolProgramsResponse])
async def update_school_programs(
    program_in: SchoolProgramsUpdate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Update languages offered by the school. This is the only endpoint that changes
    profile languages; GET /schools/profile then returns the updated data.languages.
    """
    success = await SchoolService.update_programs(
        db,
        current_user.school_id,
        program_in.languages,
    )
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to update programs (school not found or one or more language codes invalid)",
        )

    school = await SchoolService.get_school_with_languages(db, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    codes = [lang.code for lang in school.languages]
    return SuccessResponse(
        data=SchoolProgramsResponse(languages=codes),
        message="School programs updated successfully",
    )


@router.delete("/program/{language_code}", response_model=SuccessResponse[SchoolProgramsResponse])
async def remove_school_program(
    language_code: str,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
) -> Any:
    """
    Remove one language from the school's offered languages. Admin only.
    """
    success = await SchoolService.remove_program(
        db, current_user.school_id, language_code
    )
    if not success:
        raise HTTPException(
            status_code=404,
            detail="Language not found or not offered by this school",
        )
    school = await SchoolService.get_school_with_languages(db, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    codes = [lang.code for lang in school.languages]
    return SuccessResponse(
        data=SchoolProgramsResponse(languages=codes),
        message="Language removed successfully",
    )


@router.post("/logo", response_model=SuccessResponse[SchoolResponse])
async def upload_school_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Upload branding logo to storage (Cloudflare R2).
    """
    if file.content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=400, detail="Invalid file type")

    content = await file.read()
    key_prefix = f"logos/{current_user.school_id}"
    try:
        logo_url = await storage.upload(
            key_prefix, file.filename or "logo", content, content_type=file.content_type
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Update school record and ensure it persists
    school = await SchoolService.update_school(
        db,
        current_user.school_id,
        SchoolUpdate(logo_url=logo_url),
    )
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    school = await SchoolService.get_school_with_languages(db, current_user.school_id)
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    return SuccessResponse(
        data=school,
        message="Logo uploaded successfully",
    )


@router.get("/terms", response_model=SuccessResponse)
async def get_terms(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List all terms for current school.
    """
    terms = await SchoolService.get_terms(db, current_user.school_id)
    data = [
        {
            "id": str(t.id),
            "name": t.name,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "is_active": t.is_active
        }
        for t in terms
    ]
    return SuccessResponse(data=data)


@router.get("/bills", response_model=PaginatedResponse[BillResponse])
async def list_school_bills(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> Any:
    """
    List billing history for the school (Figma: Billing / Billing History table).
    Admin only. Returns Date (due_date), Amount, Status; frontend can add View Receipt when receipt_url is available.
    """
    bills, total = await BillingService.list_bills(
        db, current_user.school_id, page=page, page_size=page_size
    )
    total_pages = (total + page_size - 1) // page_size if total else 0
    return PaginatedResponse(
        data=[BillResponse.model_validate(b) for b in bills],
        meta=PaginationMeta(page=page, page_size=page_size, total=total, total_pages=total_pages),
        message="Billing history retrieved successfully",
    )
