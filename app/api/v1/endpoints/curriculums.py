from typing import Any, List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
import json

from app.api import deps
from app.models.user import User
from app.services.curriculum_service import CurriculumService
from app.services import storage_service as storage
from app.schemas.content import (
    CurriculumResponse, CurriculumCreate, CurriculumUpdate, 
    CurriculumMergeProposeRequest, CurriculumMergeConfirmRequest, MergeProposalResponse,
    TopicUpdate, TopicResponse, CurriculumGenerateRequest
)
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
                classes=[{"id": cls.id, "name": cls.name} for cls in c.classes],
                topics=[
                    TopicResponse(
                        id=t.id,
                        title=t.title,
                        content=t.content,
                        duration_hours=t.duration_hours,
                        learning_objectives=t.learning_objectives,
                        order_index=t.order_index
                    ) for t in c.topics
                ] if getattr(c, 'topics', None) else []
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

    content = await file.read()
    key_prefix = f"curriculums/{current_user.school_id}"
    try:
        file_url = await storage.upload(
            key_prefix, file.filename or "document.pdf", content, content_type=file.content_type
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

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
        classes=[{"id": cls.id, "name": cls.name} for cls in new_curriculum.classes],
        topics=[]
    )
    
    return SuccessResponse(data=data, message="Curriculum uploaded successfully")

@router.post("/generate", response_model=SuccessResponse[List[TopicResponse]])
async def generate_curriculum(
    generate_in: CurriculumGenerateRequest,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Generate a full curriculum structure from a text prompt.
    """
    topics_create = await CurriculumService.generate_curriculum_topics(
        db, generate_in.prompt, generate_in.language_id
    )
    
    import uuid
    data = [
        TopicResponse(
            id=uuid.uuid4(), # Return temporary IDs for UI tracking before persistence
            title=t.title,
            content=t.content,
            duration_hours=t.duration_hours,
            learning_objectives=t.learning_objectives,
            order_index=t.order_index
        ) for t in topics_create
    ]
    return SuccessResponse(data=data, message="Curriculum generated successfully")

@router.post("/{curriculum_id}/extract", response_model=SuccessResponse[List[TopicResponse]])
async def extract_topics(
    curriculum_id: UUID,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Trigger AI extraction of topics for a newly uploaded curriculum document.
    """
    # Fetch Curriculum to ensure it exists and we have permissions
    curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, current_user.school_id)
    if not curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
        
    if not curriculum.file_url:
        raise HTTPException(status_code=400, detail="Curriculum has no document to extract from")
    
    # Use the real document URL for extraction
    topics = await CurriculumService.extract_topics(db, curriculum_id, curriculum.file_url)
    
    data = [
        TopicResponse(
            id=t.id,
            title=t.title,
            content=t.content,
            duration_hours=t.duration_hours,
            learning_objectives=t.learning_objectives,
            order_index=t.order_index
        ) for t in topics
    ]
    return SuccessResponse(data=data, message="Topics extracted successfully")

@router.patch("/topics/{topic_id}", response_model=SuccessResponse[TopicResponse])
async def update_topic(
    topic_id: UUID,
    topic_in: TopicUpdate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Teacher modification of an AI-generated topic.
    """
    # Note: Ideally add a check that the topic belongs to the user's school
    updated = await CurriculumService.update_topic(db, topic_id, topic_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Topic not found")
        
    data = TopicResponse(
        id=updated.id,
        title=updated.title,
        content=updated.content,
        duration_hours=updated.duration_hours,
        learning_objectives=updated.learning_objectives,
        order_index=updated.order_index
    )
    return SuccessResponse(data=data, message="Topic updated successfully")

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
        classes=[{"id": cls.id, "name": cls.name} for cls in curriculum.classes],
        topics=[
            TopicResponse(
                id=t.id,
                title=t.title,
                content=t.content,
                duration_hours=t.duration_hours,
                learning_objectives=t.learning_objectives,
                order_index=t.order_index
            ) for t in curriculum.topics
        ] if getattr(curriculum, 'topics', None) else []
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
        classes=[{"id": cls.id, "name": cls.name} for cls in updated.classes],
        topics=[
            TopicResponse(
                id=t.id,
                title=t.title,
                content=t.content,
                duration_hours=t.duration_hours,
                learning_objectives=t.learning_objectives,
                order_index=t.order_index
            ) for t in updated.topics
        ] if getattr(updated, 'topics', None) else []
    )
    return SuccessResponse(data=data, message="Curriculum updated successfully")

@router.post("/{curriculum_id}/merge/propose", response_model=SuccessResponse[MergeProposalResponse])
async def propose_merge(
    curriculum_id: UUID,
    merge_in: CurriculumMergeProposeRequest,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Trigger AI to propose a unified merge structure between two curriculums."""
    teacher_curriculum = await CurriculumService.get_curriculum_by_id(db, curriculum_id, current_user.school_id)
    library_curriculum = await CurriculumService.get_curriculum_by_id(db, merge_in.library_curriculum_id, current_user.school_id)
    
    if not teacher_curriculum or not library_curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
        
    proposals = await CurriculumService.propose_merge_strategy(db, teacher_curriculum, library_curriculum)
    
    import uuid
    data = MergeProposalResponse(
        proposal_id=uuid.uuid4(),
        proposed_topics=proposals
    )
    return SuccessResponse(data=data, message="Merge proposal generated")

@router.post("/{curriculum_id}/merge/confirm", response_model=SuccessResponse[CurriculumResponse])
async def confirm_merge(
    curriculum_id: UUID,
    merge_in: CurriculumMergeConfirmRequest,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """Finalize the merge with teacher-selected topics and create the new curriculum."""
    merged = await CurriculumService.confirm_merge(
        db, current_user.school_id, curriculum_id, merge_in.final_topics
    )
    
    data = CurriculumResponse(
        id=merged.id,
        title=merged.title,
        description=merged.description,
        source_type=merged.source_type,
        file_url=merged.file_url,
        status=merged.status,
        created_at=merged.created_at,
        language_name=merged.language.name if merged.language else None,
        classes=[{"id": cls.id, "name": cls.name} for cls in merged.classes],
        topics=[
            TopicResponse(
                id=t.id,
                title=t.title,
                content=t.content,
                duration_hours=t.duration_hours,
                learning_objectives=t.learning_objectives,
                order_index=t.order_index
            ) for t in merged.topics
        ] if getattr(merged, 'topics', None) else []
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
