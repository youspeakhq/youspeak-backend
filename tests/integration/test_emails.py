"""Integration tests for email sending API"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.models.user import User
from app.models.communication import EmailLog
from app.models.enums import UserRole, EmailSendStatus


@pytest.mark.asyncio
class TestEmailSendingAPI:
    """Test email sending endpoint"""

    async def test_emails_router_accessible(self, async_client: AsyncClient):
        """Test that emails router is accessible at all"""
        response = await async_client.get("/api/v1/emails/test")
        assert response.status_code == 200, f"Debug endpoint returned {response.status_code}: {response.text}"
        data = response.json()
        assert data["message"] == "Emails router is working"

    @pytest.fixture
    async def teacher_user(self, db: AsyncSession, registered_school, unique_suffix: str):
        """Create a test teacher user"""
        from app.models.user import User
        from app.core.security import get_password_hash
        from app.models.enums import UserRole
        from uuid import UUID

        user = User(
            email=f"teacher_{unique_suffix}@test.com",
            hashed_password=get_password_hash("password123"),
            first_name="Test",
            last_name="Teacher",
            role=UserRole.TEACHER,
            school_id=UUID(registered_school["school_id"]),
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @pytest.fixture
    async def auth_headers(self, teacher_user):
        """Get authentication headers for teacher"""
        from app.core.security import create_access_token
        from app.models.enums import UserRole

        # Include role in token (matching production behavior)
        token = create_access_token({"sub": str(teacher_user.id), "role": UserRole.TEACHER.value})
        return {"Authorization": f"Bearer {token}"}

    async def test_send_email_single_recipient_success(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession, teacher_user
    ):
        """Test sending email to single recipient"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["student@example.com"],
                    "subject": "Test Email",
                    "html_body": "<html><body><h1>Test</h1></body></html>",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_recipients"] == 1
        assert data["data"]["successful_sends"] == 1
        assert data["data"]["failed_sends"] == 0
        assert len(data["data"]["results"]) == 1
        assert data["data"]["results"][0]["status"] == "sent"
        assert "email_log_id" in data["data"]

        # Verify email log was created
        from sqlalchemy import select
        stmt = select(EmailLog).where(EmailLog.sender_id == teacher_user.id)
        result = await db.execute(stmt)
        email_log = result.scalar_one()
        assert email_log.send_status == EmailSendStatus.SENT
        assert email_log.recipients == ["student@example.com"]
        assert email_log.subject == "Test Email"
        assert email_log.sent_at is not None

    async def test_send_email_multiple_recipients_success(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession, teacher_user
    ):
        """Test sending email to multiple recipients"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": [
                        "student1@example.com",
                        "student2@example.com",
                        "student3@example.com",
                    ],
                    "subject": "Assignment Reminder",
                    "html_body": "<html><body><p>Please complete your assignment.</p></body></html>",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["total_recipients"] == 3
        assert data["data"]["successful_sends"] == 3
        assert data["data"]["failed_sends"] == 0
        assert len(data["data"]["results"]) == 3
        for result in data["data"]["results"]:
            assert result["status"] == "sent"

    async def test_send_email_partial_failure(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession, teacher_user
    ):
        """Test sending email with partial failures"""
        def mock_send_side_effect(to_email, subject, html, reply_to=None):
            # Fail for second recipient
            if to_email == "fail@example.com":
                return False
            return True

        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.side_effect = mock_send_side_effect

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": [
                        "success1@example.com",
                        "fail@example.com",
                        "success2@example.com",
                    ],
                    "subject": "Test",
                    "html_body": "<html><body>Test</body></html>",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["successful_sends"] == 2
        assert data["data"]["failed_sends"] == 1

        # Check individual results
        results = {r["recipient"]: r for r in data["data"]["results"]}
        assert results["success1@example.com"]["status"] == "sent"
        assert results["fail@example.com"]["status"] == "failed"
        assert results["success2@example.com"]["status"] == "sent"

        # Verify email log status
        from sqlalchemy import select
        stmt = select(EmailLog).where(EmailLog.sender_id == teacher_user.id)
        result = await db.execute(stmt)
        email_log = result.scalar_one()
        assert email_log.send_status == EmailSendStatus.SENT  # Mixed status still sent
        assert "1/3 recipients failed" in email_log.error_message

    async def test_send_email_with_reply_to(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession
    ):
        """Test sending email with reply_to address"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["student@example.com"],
                    "subject": "Test",
                    "html_body": "<html><body>Test</body></html>",
                    "reply_to": "teacher@school.com",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        # Verify reply_to was passed to send_email
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args[1]
        assert call_kwargs["reply_to"] == "teacher@school.com"

    async def test_send_email_validation_errors(
        self, async_client: AsyncClient, api_base: str, auth_headers
    ):
        """Test validation errors for email requests"""

        # Test: no recipients
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": [],
                "subject": "Test",
                "html_body": "<html><body>Test</body></html>",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Test: too many recipients (>10)
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": [f"user{i}@example.com" for i in range(15)],
                "subject": "Test",
                "html_body": "<html><body>Test</body></html>",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Test: subject too long (>200 chars)
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": ["test@example.com"],
                "subject": "A" * 201,
                "html_body": "<html><body>Test</body></html>",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Test: HTML body too large (>500KB)
        large_html = "<html><body>" + "X" * 500_001 + "</body></html>"
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": ["test@example.com"],
                "subject": "Test",
                "html_body": large_html,
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

        # Test: invalid email format
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": ["invalid-email"],
                "subject": "Test",
                "html_body": "<html><body>Test</body></html>",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    async def test_send_email_requires_authentication(self, async_client: AsyncClient, api_base: str):
        """Test that endpoint requires authentication"""
        response = await async_client.post(
            f"{api_base}/emails/send",
            json={
                "recipients": ["test@example.com"],
                "subject": "Test",
                "html_body": "<html><body>Test</body></html>",
            },
        )
        assert response.status_code == 401

    async def test_send_email_rate_limit_teacher(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession
    ):
        """Test rate limiting for teachers (10 emails per hour)"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            # Send 10 emails (should all succeed for teacher)
            for i in range(10):
                response = await async_client.post(
                    f"{api_base}/emails/send",
                    json={
                        "recipients": [f"test{i}@example.com"],
                        "subject": f"Test {i}",
                        "html_body": "<html><body>Test</body></html>",
                    },
                    headers=auth_headers,
                )
                assert response.status_code == 200

            # 11th email should be rate limited
            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["test11@example.com"],
                    "subject": "Test 11",
                    "html_body": "<html><body>Test</body></html>",
                },
                headers=auth_headers,
            )
            assert response.status_code == 429

    async def test_send_email_rate_limit_student(
        self, async_client: AsyncClient, api_base: str, db: AsyncSession, registered_school, unique_suffix: str
    ):
        """Test rate limiting for students (3 emails per hour)"""
        # Create a student user
        from app.models.user import User
        from app.core.security import get_password_hash, create_access_token
        from app.models.enums import UserRole
        from uuid import UUID

        student = User(
            email=f"student_{unique_suffix}@test.com",
            hashed_password=get_password_hash("password123"),
            first_name="Test",
            last_name="Student",
            role=UserRole.STUDENT,
            school_id=UUID(registered_school["school_id"]),
        )
        db.add(student)
        await db.commit()
        await db.refresh(student)

        # Create token with role
        token = create_access_token({"sub": str(student.id), "role": UserRole.STUDENT.value})
        student_headers = {"Authorization": f"Bearer {token}"}

        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            # Send 3 emails (should all succeed for student)
            for i in range(3):
                response = await async_client.post(
                    f"{api_base}/emails/send",
                    json={
                        "recipients": [f"test{i}@example.com"],
                        "subject": f"Test {i}",
                        "html_body": "<html><body>Test</body></html>",
                    },
                    headers=student_headers,
                )
                assert response.status_code == 200

            # 4th email should be rate limited
            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["test4@example.com"],
                    "subject": "Test 4",
                    "html_body": "<html><body>Test</body></html>",
                },
                headers=student_headers,
            )
            assert response.status_code == 429

    async def test_send_email_audit_trail(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession, teacher_user
    ):
        """Test that email audit trail is created correctly"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = True

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["student1@example.com", "student2@example.com"],
                    "subject": "Important Announcement",
                    "html_body": "<html><body><h1>Please read this</h1></body></html>",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        email_log_id = data["data"]["email_log_id"]

        # Verify email log in database
        from sqlalchemy import select
        stmt = select(EmailLog).where(EmailLog.id == email_log_id)
        result = await db.execute(stmt)
        email_log = result.scalar_one()

        assert email_log.sender_id == teacher_user.id
        assert email_log.school_id == teacher_user.school_id
        assert email_log.recipients == ["student1@example.com", "student2@example.com"]
        assert email_log.subject == "Important Announcement"
        assert len(email_log.html_body_sha256) == 64  # SHA256 hash length
        assert email_log.send_status == EmailSendStatus.SENT
        assert email_log.sent_at is not None
        assert email_log.error_message is None

    async def test_send_email_all_failures(
        self, async_client: AsyncClient, api_base: str, auth_headers, db: AsyncSession, teacher_user
    ):
        """Test sending email when all recipients fail"""
        with patch("app.services.email_service.send_email") as mock_send:
            mock_send.return_value = False

            response = await async_client.post(
                f"{api_base}/emails/send",
                json={
                    "recipients": ["fail1@example.com", "fail2@example.com"],
                    "subject": "Test",
                    "html_body": "<html><body>Test</body></html>",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["successful_sends"] == 0
        assert data["data"]["failed_sends"] == 2

        # Verify email log status is FAILED
        from sqlalchemy import select
        stmt = select(EmailLog).where(EmailLog.sender_id == teacher_user.id)
        result = await db.execute(stmt)
        email_log = result.scalar_one()
        assert email_log.send_status == EmailSendStatus.FAILED
        assert email_log.error_message == "All recipients failed"
