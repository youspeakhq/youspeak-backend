from typing import Any, List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api import deps
from app.models.onboarding import Language
from app.schemas.school import LanguageResponse
from app.schemas.responses import SuccessResponse

router = APIRouter()

@router.get("/languages", response_model=SuccessResponse[List[LanguageResponse]])
async def get_global_languages(
    db: AsyncSession = Depends(deps.get_db)
) -> Any:
    """
    Global list (e.g., French, Spanish).
    """
    result = await db.execute(select(Language))
    languages = result.scalars().all()
    return SuccessResponse(data=languages)
