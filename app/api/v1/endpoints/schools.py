from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api import deps
from app.models.user import User
from app.services.school_service import SchoolService
from app.schemas.school import SchoolResponse, SchoolUpdate, SchoolProgramsUpdate
from app.schemas.responses import SuccessResponse

router = APIRouter()

@router.get("/profile", response_model=SuccessResponse[SchoolResponse])
async def get_school_profile(
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Fetch school details. Admin only.
    """
    school = await SchoolService.get_school_by_id(db, current_user.school_id)
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
        
    return SuccessResponse(data=school, message="Profile updated successfully")

@router.put("/program", response_model=SuccessResponse[dict])
async def update_school_programs(
    program_in: SchoolProgramsUpdate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Update languages offered.
    """
    success = await SchoolService.update_programs(
        db, 
        current_user.school_id, 
        program_in.languages
    )
    if not success:
        raise HTTPException(status_code=400, detail="Failed to update programs")
        
    return SuccessResponse(data={"languages": program_in.languages}, message="School programs updated successfully")

@router.post("/logo", response_model=SuccessResponse)
async def upload_school_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Upload branding logo.
    """
    # TODO: Implement actual S3/storage upload
    # For now mock it
    
    # Verify file type
    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Invalid file type")
        
    logo_url = f"https://s3.youspeak.com/logos/{current_user.school_id}/{file.filename}"
    
    # Update school record
    await SchoolService.update_school(
        db, 
        current_user.school_id, 
        SchoolUpdate(logo_url=logo_url)
    )
    
    return SuccessResponse(
        data={"url": logo_url},
        message="Logo uploaded successfully"
    )

@router.get("/semesters", response_model=SuccessResponse)
async def get_semesters(
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    List all semesters for current school.
    """
    semesters = await SchoolService.get_semesters(db, current_user.school_id)
    data = [
        {
            "id": str(s.id),
            "name": s.name,
            "start_date": s.start_date,
            "end_date": s.end_date,
            "is_active": s.is_active
        } 
        for s in semesters
    ]
    return SuccessResponse(data=data)
