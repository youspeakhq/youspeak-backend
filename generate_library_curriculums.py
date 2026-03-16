#!/usr/bin/env python3
"""
Generate library curriculum data for testing.
Usage: python3 generate_library_curriculums.py
"""

import os
import asyncio
import sys
from uuid import UUID

# Add the services/curriculum directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'services', 'curriculum'))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from models.curriculum import Curriculum
from models.enums import CurriculumStatus, CurriculumSourceType


async def create_library_curriculums():
    """Create sample library curriculum data."""

    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        print("Usage: DATABASE_URL='postgresql+asyncpg://...' python3 generate_library_curriculums.py")
        return

    # Create engine and session
    engine = create_async_engine(database_url, echo=True)
    AsyncSessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # School ID (replace with actual from staging)
    school_id = UUID('1738bd06-2b9d-4e72-9737-42c2e39a75f1')

    # Library curriculums to create
    library_curriculums = [
        {
            'title': 'French for Beginners - A1 Level',
            'description': 'Official YouSpeak library curriculum for absolute beginners in French. Master basic greetings, numbers 1-100, and everyday conversations.',
            'language_id': 1,  # French
        },
        {
            'title': 'Spanish for Beginners - A1 Level',
            'description': 'Official YouSpeak library curriculum. Learn Spanish basics including greetings, introductions, and common phrases.',
            'language_id': 2,  # Spanish (adjust if different)
        },
        {
            'title': 'Business English - B2 Level',
            'description': 'Official YouSpeak library curriculum for professional English. Focus on business communication, presentations, and negotiations.',
            'language_id': 3,  # English (adjust if different)
        },
        {
            'title': 'French Intermediate - A2 Level',
            'description': 'Official YouSpeak library curriculum for intermediate learners. Covers past tense, future planning, and complex conversations.',
            'language_id': 1,  # French
        },
        {
            'title': 'German for Beginners - A1 Level',
            'description': 'Official YouSpeak library curriculum. Learn German alphabet, basic grammar, and essential vocabulary for daily life.',
            'language_id': 4,  # German (adjust if different)
        },
    ]

    async with AsyncSessionLocal() as session:
        try:
            created_count = 0
            for curr_data in library_curriculums:
                curriculum = Curriculum(
                    school_id=school_id,
                    title=curr_data['title'],
                    description=curr_data['description'],
                    language_id=curr_data['language_id'],
                    source_type=CurriculumSourceType.LIBRARY_MASTER,
                    status=CurriculumStatus.PUBLISHED,
                )
                session.add(curriculum)
                created_count += 1
                print(f"✅ Created: {curr_data['title']}")

            await session.commit()
            print(f"\n🎉 Successfully created {created_count} library curriculums!")

        except Exception as e:
            print(f"\n❌ Error creating library curriculums: {e}")
            await session.rollback()
        finally:
            await engine.dispose()


if __name__ == '__main__':
    print("=" * 60)
    print("Library Curriculum Generator")
    print("=" * 60)
    print()
    asyncio.run(create_library_curriculums())
