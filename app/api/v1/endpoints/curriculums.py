from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json

from app.api import deps
from app.models.user import User
from app.services.curriculum_service import CurriculumService
from app.schemas.content import CurriculumResponse, CurriculumCreate, CurriculumUpdate, CurriculumMergeRequest
from app.schemas.responses import SuccessResponse, PaginatedResponse
from app.models.enums import CurriculumStatus

router = APIRouter()

@router.get("", response_model=PaginatedResponse[CurriculumResponse])
async def list_curriculums(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[CurriculumStatus] = Query(None),
    language_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(deps.require_admin), # Schools usually have curriculum managed by admins
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Get paginated list of curriculums for the school.
    """
    skip = (page - 1) * page_size
    curriculums, total = await CurriculumService.get_curriculums(
        db, 
        current_user.school_id, 
        skip=skip, 
        limit=page_size,
        status=status,
        language_id=language_id,
        search=search
    )
    
    # Format response
    serialized = []
    for c in curriculums:
        serialized.append(
            CurriculumResponse(
                id=c.id,
                title=c.title,
                description=c.description,
                source_type=c.source_type,
                file_url=c.file_url,
                status=c.status,
                created_at=c.created_at,
                language_name=c.language.name if c.language else None,
                classes=[{"id": cls.id, "name": cls.name} for cls in c.classes]
            )
        )
        
    total_pages = (total + page_size - 1) // page_size
    
    return PaginatedResponse(
        data=serialized,
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    )

@router.post("", response_model=SuccessResponse[CurriculumResponse])
async def upload_curriculum(
    title: str = Form(...),
    language_id: int = Form(...),
    description: Optional[str] = Form(None),
    class_ids_json: Optional[str] = Form(None), # JSON string list of UUIDs
    file: UploadFile = File(...),
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Upload a new curriculum file and assign to classes.
    """
    # Parse class IDs if provided
    class_ids = []
    if class_ids_json:
        try:
            class_ids = [UUID(cid) for cid in json.loads(class_ids_json)]
        except (ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=400, detail="Invalid class_ids format")

    # Mock file upload logic - in production this would save to S3/GCS
    file_url = f"https://storage.youspeak.com/curriculums/{current_user.school_id}/{file.filename}"
    
    curriculum_in = CurriculumCreate(
        title=title,
        language_id=language_id,
        description=description,
        class_ids=class_ids
    )
    
    new_curriculum = await CurriculumService.create_curriculum(
        db, current_user.school_id, curriculum_in, file_url=file_url
    )
    # Final serialization for response (including relationships fetched by service)
    data = CurriculumResponse(
        id=new_curriculum.id,
        title=new_curriculum.title,
        description=new_curriculum.description,
        source_type=new_curriculum.source_type,
        file_url=new_curriculum.file_url,
        status=new_curriculum.status,
        created_at=new_curriculum.created_at,
        language_name=new_curriculum.language.name if new_curriculum.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in new_curriculum.classes]
    )
    
    return SuccessResponse(data=data, message="Curriculum uploaded successfully")

@router.get("/{curriculum_id}", response_model=SuccessResponse[CurriculumResponse])
async def get_curriculum(
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Get details of a specific curriculum."""
    curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, current_user.school_id)
    if not curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
        
    data = CurriculumResponse(
        id=curriculum.id,
        title=curriculum.title,
        description=curriculum.description,
        source_type=curriculum.source_type,
        file_url=curriculum.file_url,
        status=curriculum.status,
        created_at=curriculum.created_at,
        language_name=curriculum.language.name if curriculum.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in curriculum.classes]
    )
    return SuccessResponse(data=data)

@router.patch("/{curriculum_id}", response_model=SuccessResponse[CurriculumResponse])
async def update_curriculum(
    curriculum_id: UUID,
    curriculum_in: CurriculumUpdate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Update curriculum title, status, or class assignments."""
    updated = await CurriculumService.update_curriculum(
        db, curriculum_id, current_user.school_id, curriculum_in
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Curriculum not found")
        
    data = CurriculumResponse(
        id=updated.id,
        title=updated.title,
        description=updated.description,
        source_type=updated.source_type,
        file_url=updated.file_url,
        status=updated.status,
        created_at=updated.created_at,
        language_name=updated.language.name if updated.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in updated.classes]
    )
    return SuccessResponse(data=data, message="Curriculum updated successfully")

@router.post("/{curriculum_id}/merge", response_model=SuccessResponse[CurriculumResponse])
async def merge_curriculum(
    curriculum_id: UUID,
    merge_in: CurriculumMergeRequest,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Merge teacher content with inbuilt library content."""
    merged = await CurriculumService.merge_curriculum(
        db, curriculum_id, current_user.school_id, strategy=merge_in.strategy
    )
    if not merged:
        raise HTTPException(status_code=404, detail="Curriculum not found")
        
    data = CurriculumResponse(
        id=merged.id,
        title=merged.title,
        description=merged.description,
        source_type=merged.source_type,
        file_url=merged.file_url,
        status=merged.status,
        created_at=merged.created_at,
        language_name=merged.language.name if merged.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in merged.classes]
    )
    return SuccessResponse(data=data, message="Curriculum merged successfully")

@router.delete("/{curriculum_id}", response_model=SuccessResponse)
async def delete_curriculum(
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Permanently delete a curriculum."""
    success = await CurriculumService.delete_curriculum(db, curriculum_id, current_user.school_id)
    if not success:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    return SuccessResponse(data=None, message="Curriculum deleted successfully")
