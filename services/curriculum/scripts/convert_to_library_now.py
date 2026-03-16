#!/usr/bin/env python3
"""
Convert teacher_upload curriculums to library_master type.
Run this script with DATABASE_URL environment variable set.
"""

import os
import sys
import asyncio

# Ensure we can import from parent directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from database import engine


async def convert_to_library(count=2):
    """Convert teacher curriculums to library type."""

    print(f"Converting {count} curriculums to library_master type...")
    print()

    async with engine.begin() as conn:
        # Convert curriculums
        result = await conn.execute(text("""
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
                ELSE COALESCE(description, '')
              END,
              status = 'published'
            WHERE id IN (
              SELECT id
              FROM curriculums
              WHERE source_type = 'teacher_upload'
              ORDER BY created_at DESC
              LIMIT :count
            )
            RETURNING id, title, source_type, status;
        """), {"count": count})

        converted = result.fetchall()

        if not converted:
            print("❌ No teacher_upload curriculums found to convert!")
            return

        print(f"✅ Successfully converted {len(converted)} curriculums:")
        print()
        for row in converted:
            print(f"  • {row.title}")
            print(f"    Source: {row.source_type} | Status: {row.status}")
            print()

        # Show final counts
        count_result = await conn.execute(text("""
            SELECT source_type, COUNT(*) as count
            FROM curriculums
            GROUP BY source_type
            ORDER BY source_type;
        """))

        print("📊 Final curriculum counts by source type:")
        for row in count_result:
            print(f"  • {row.source_type}: {row.count}")

    print()
    print("✅ Done! Library curriculums created successfully.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Convert curriculums to library type')
    parser.add_argument('--count', type=int, default=2, help='Number of curriculums to convert (default: 2)')
    args = parser.parse_args()

    # Check DATABASE_URL
    if not os.getenv('DATABASE_URL'):
        print("❌ ERROR: DATABASE_URL environment variable not set")
        print()
        print("Usage:")
        print("  export DATABASE_URL='postgresql+asyncpg://...'")
        print("  python3 convert_to_library_now.py --count 2")
        sys.exit(1)

    asyncio.run(convert_to_library(args.count))
