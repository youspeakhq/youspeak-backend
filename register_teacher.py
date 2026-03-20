"""Script to register a teacher"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.onboarding import School
from app.models.access_code import TeacherAccessCode
from app.services.user_service import UserService


async def main():
    async with AsyncSessionLocal() as db:
        # Check for available schools and access codes
        result = await db.execute(select(School).limit(5))
        schools = result.scalars().all()

        print("=== Available Schools ===")
        for school in schools:
            print(f"ID: {school.id}, Name: {school.name}")

        # Check for unused access codes
        result = await db.execute(
            select(TeacherAccessCode).where(TeacherAccessCode.is_used == False).limit(10)
        )
        codes = result.scalars().all()

        print("\n=== Available Access Codes ===")
        for code in codes:
            print(f"Code: {code.code}, School ID: {code.school_id}, Used: {code.is_used}")

        if not codes:
            print("\nNo available access codes found. You need to create one first.")
            return

        # Use the first available code
        access_code = codes[0].code

        print(f"\n=== Registering Teacher ===")
        print("Email: mbakaragoodness2003@gmail.com")
        print(f"First Name: Goodness")
        print(f"Last Name: Mbakara")
        print(f"Access Code: {access_code}")

        teacher = await UserService.create_teacher_with_code(
            db=db,
            code=access_code,
            email="mbakaragoodness2003@gmail.com",
            password="MISSERUN123a#",
            first_name="Goodness",
            last_name="Mbakara"
        )

        if teacher:
            await db.commit()
            print(f"\n✅ Teacher registered successfully!")
            print(f"User ID: {teacher.id}")
            print(f"School ID: {teacher.school_id}")
            print(f"Email: {teacher.email}")
        else:
            print("\n❌ Failed to register teacher. Check if email already exists or access code is invalid.")


if __name__ == "__main__":
    asyncio.run(main())
