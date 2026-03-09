"""Admin-only routes for data management."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from database import get_db
from api.deps import get_school_id

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/migrate-to-library")
async def convert_to_library_curriculums(
    count: int = 2,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Convert teacher_upload curriculums to library_master type.
    This is a one-time migration utility for testing.

    WARNING: This modifies curriculum data. Use with caution!
    """

    sql = text("""
        UPDATE curriculums
        SET
          source_type = 'library_master',
          title = CASE
            WHEN title NOT LIKE '[LIBRARY]%%' THEN '[LIBRARY] ' || title
            ELSE title
          END,
          description = CASE
            WHEN COALESCE(description, '') NOT LIKE 'Official YouSpeak Library%%'
            THEN 'Official YouSpeak Library Content - ' || COALESCE(description, '')
            ELSE description
          END,
          status = 'published'
        WHERE id IN (
          SELECT id
          FROM curriculums
          WHERE source_type = 'teacher_upload'
          LIMIT :count
        )
        RETURNING id, title, source_type, status;
    """)

    result = await db.execute(sql, {"count": count})
    converted = result.fetchall()

    # Get final counts
    count_sql = text("""
        SELECT source_type, COUNT(*) as count
        FROM curriculums
        GROUP BY source_type
        ORDER BY source_type;
    """)
    count_result = await db.execute(count_sql)
    counts = {row.source_type: row.count for row in count_result}

    await db.commit()

    return {
        "success": True,
        "message": f"Converted {len(converted)} curriculums to library_master",
        "converted": [
            {
                "id": str(row.id),
                "title": row.title,
                "source_type": row.source_type,
                "status": row.status
            }
            for row in converted
        ],
        "totals": counts
    }
