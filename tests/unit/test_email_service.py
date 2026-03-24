"""Unit tests for email service functions"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.email_service import _hash_html_body, send_bulk_email
from app.models.enums import EmailSendStatus


def test_hash_html_body():
    """Test HTML body hashing function"""
    html = "<html><body><h1>Test Email</h1></body></html>"
    hash_result = _hash_html_body(html)

    # SHA256 hash should be 64 characters
    assert len(hash_result) == 64
    # Should be hexadecimal
    assert all(c in "0123456789abcdef" for c in hash_result)

    # Same input should produce same hash
    assert _hash_html_body(html) == hash_result

    # Different input should produce different hash
    different_html = "<html><body><h1>Different Email</h1></body></html>"
    assert _hash_html_body(different_html) != hash_result


@pytest.mark.asyncio
async def test_send_bulk_email_all_success():
    """Test send_bulk_email when all emails succeed"""
    # Mock database session
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sender_id = uuid4()
    school_id = uuid4()
    recipients = ["user1@example.com", "user2@example.com"]
    subject = "Test Subject"
    html_body = "<html><body>Test</body></html>"

    with patch("app.services.email_service.send_email") as mock_send:
        mock_send.return_value = True

        email_log, results = await send_bulk_email(
            db=db,
            sender_id=sender_id,
            school_id=school_id,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

    # Verify all sends succeeded
    assert len(results) == 2
    for recipient in recipients:
        success, error = results[recipient]
        assert success is True
        assert error is None

    # Verify email log was added to session
    db.add.assert_called_once()
    # Verify flush, commit, refresh were called
    db.flush.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

    # Verify send_email was called for each recipient
    assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_send_bulk_email_partial_failure():
    """Test send_bulk_email when some emails fail"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sender_id = uuid4()
    school_id = uuid4()
    recipients = ["success@example.com", "fail@example.com", "success2@example.com"]
    subject = "Test"
    html_body = "<html><body>Test</body></html>"

    def mock_send_side_effect(to_email, subject, html, reply_to=None):
        if to_email == "fail@example.com":
            return False
        return True

    with patch("app.services.email_service.send_email") as mock_send:
        mock_send.side_effect = mock_send_side_effect

        email_log, results = await send_bulk_email(
            db=db,
            sender_id=sender_id,
            school_id=school_id,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

    # Verify results
    assert results["success@example.com"] == (True, None)
    assert results["fail@example.com"] == (False, "Email service returned false")
    assert results["success2@example.com"] == (True, None)

    # Verify send_email was called for each recipient
    assert mock_send.call_count == 3


@pytest.mark.asyncio
async def test_send_bulk_email_all_failure():
    """Test send_bulk_email when all emails fail"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sender_id = uuid4()
    school_id = None
    recipients = ["fail1@example.com", "fail2@example.com"]
    subject = "Test"
    html_body = "<html><body>Test</body></html>"

    with patch("app.services.email_service.send_email") as mock_send:
        mock_send.return_value = False

        email_log, results = await send_bulk_email(
            db=db,
            sender_id=sender_id,
            school_id=school_id,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

    # Verify all failed
    assert all(not success for success, _ in results.values())

    # Verify send_email was called for each recipient
    assert mock_send.call_count == 2


@pytest.mark.asyncio
async def test_send_bulk_email_with_reply_to():
    """Test send_bulk_email with reply_to parameter"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sender_id = uuid4()
    school_id = uuid4()
    recipients = ["user@example.com"]
    subject = "Test"
    html_body = "<html><body>Test</body></html>"
    reply_to = "teacher@school.com"

    with patch("app.services.email_service.send_email") as mock_send:
        mock_send.return_value = True

        email_log, results = await send_bulk_email(
            db=db,
            sender_id=sender_id,
            school_id=school_id,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
            reply_to=reply_to,
        )

    # Verify reply_to was passed to send_email
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args[1]
    assert call_kwargs["reply_to"] == reply_to


@pytest.mark.asyncio
async def test_send_bulk_email_exception_handling():
    """Test send_bulk_email handles exceptions gracefully"""
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    sender_id = uuid4()
    school_id = uuid4()
    recipients = ["user1@example.com", "user2@example.com"]
    subject = "Test"
    html_body = "<html><body>Test</body></html>"

    def mock_send_side_effect(to_email, subject, html, reply_to=None):
        if to_email == "user2@example.com":
            raise Exception("Network error")
        return True

    with patch("app.services.email_service.send_email") as mock_send:
        mock_send.side_effect = mock_send_side_effect

        email_log, results = await send_bulk_email(
            db=db,
            sender_id=sender_id,
            school_id=school_id,
            recipients=recipients,
            subject=subject,
            html_body=html_body,
        )

    # Verify first succeeded, second failed with error message
    assert results["user1@example.com"] == (True, None)
    success, error = results["user2@example.com"]
    assert success is False
    assert "Network error" in error


def test_send_email_with_reply_to():
    """Test send_email function with reply_to parameter"""
    from app.services.email_service import send_email

    with patch("app.services.email_service.resend") as mock_resend:
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test_key"
            mock_settings.EMAIL_FROM = "noreply@youspeak.com"
            mock_settings.ENVIRONMENT = "production"

            send_email(
                to_email="user@example.com",
                subject="Test",
                html="<html><body>Test</body></html>",
                reply_to="teacher@school.com",
            )

            # Verify Emails.send was called with reply_to
            mock_resend.Emails.send.assert_called_once()
            call_args = mock_resend.Emails.send.call_args[0][0]
            assert call_args["reply_to"] == "teacher@school.com"
            assert call_args["to"] == ["user@example.com"]
            assert call_args["subject"] == "Test"


def test_send_email_without_reply_to():
    """Test send_email function without reply_to parameter"""
    from app.services.email_service import send_email

    with patch("app.services.email_service.resend") as mock_resend:
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.RESEND_API_KEY = "test_key"
            mock_settings.EMAIL_FROM = "noreply@youspeak.com"
            mock_settings.ENVIRONMENT = "production"

            send_email(
                to_email="user@example.com",
                subject="Test",
                html="<html><body>Test</body></html>",
            )

            # Verify Emails.send was called without reply_to
            mock_resend.Emails.send.assert_called_once()
            call_args = mock_resend.Emails.send.call_args[0][0]
            assert "reply_to" not in call_args
            assert call_args["to"] == ["user@example.com"]
