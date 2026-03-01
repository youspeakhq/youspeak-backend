from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.onboarding import Language
from app.models.user import User
from app.schemas.school import LanguageResponse, LanguageCreate
from app.schemas.responses import SuccessResponse
from app.services.school_service import SchoolService

router = APIRouter()


@router.get("/languages", response_model=SuccessResponse[List[LanguageResponse]])
async def get_global_languages(
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Get all active languages available on the platform.
    """
    result = await db.execute(select(Language).where(Language.is_active.is_(True)))
    languages = result.scalars().all()
    return SuccessResponse(data=languages)


@router.post("/languages", response_model=SuccessResponse[LanguageResponse], status_code=status.HTTP_201_CREATED)
async def create_language(
    language_in: LanguageCreate,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Create a new global language (admin only).

    Requires:
    - name: Language name (e.g., "German", "Mandarin")
    - code: ISO 639-1 two-letter lowercase code (e.g., "de", "zh")

    Returns 400 if a language with the same name or code already exists.
    """
    language = await SchoolService.create_language(
        db,
        name=language_in.name,
        code=language_in.code
    )

    if not language:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Language with name '{language_in.name}' or code '{language_in.code}' already exists"
        )

    data = LanguageResponse.model_validate(language)
    await db.commit()
    return SuccessResponse(data=data, message="Language created successfully")


@router.delete("/languages/{language_id}", response_model=SuccessResponse)
async def delete_language(
    language_id: int,
    current_user: User = Depends(deps.require_admin),
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Soft delete a language by setting is_active=False (admin only).

    Deletion is blocked if the language is currently in use by any:
    - Schools (in school_languages)
    - Classes
    - Classrooms

    Returns 404 if language not found.
    Returns 400 with usage counts if language is in use.
    """
    result = await SchoolService.delete_language(db, language_id)

    if not result["found"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Language with id {language_id} not found"
        )

    if result["in_use"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot delete language: currently in use by "
                f"{result['schools_count']} school(s), "
                f"{result['classes_count']} class(es), "
                f"and {result['classrooms_count']} classroom(s)"
            )
        )

    await db.commit()
    return SuccessResponse(
        data=None,
        message="Language deleted successfully"
    )
