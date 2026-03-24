"""Email service for transactional emails (Resend).

No mocks: all sends go through the Resend API when RESEND_API_KEY is set and
the recipient is not skipped (see _should_skip_email). Skip only when
ENVIRONMENT is "test" or recipient is a test domain (@test.com, @test.example.com,
@resend.dev) so tests never send real mail.

Other services can call send_email(to, subject, html) or the convenience
functions (send_teacher_invite, send_password_reset). Templates use
Figma-derived branding from email_branding.

To send to any recipient, verify a domain at resend.com/domains and set
EMAIL_FROM to an address at that domain.
"""

import logging
from urllib.parse import urlencode

from app.config import settings

try:
    from app.services.email_branding import (
        BUTTON_STYLE,
        CODE_STYLE,
        PRIMARY_HEX,
        TEXT_MUTED_HEX,
        TEXT_PRIMARY_HEX,
        FONT_FAMILY,
    )
except ModuleNotFoundError:
    # Fallback when email_branding.py is not present (e.g. CI before file is committed)
    PRIMARY_HEX = "#4B0082"
    TEXT_PRIMARY_HEX = "#1E293B"
    TEXT_MUTED_HEX = "#64748B"
    FONT_FAMILY = "Space Grotesk, system-ui, sans-serif"
    BUTTON_STYLE = (
        f"background: {PRIMARY_HEX}; color: white; padding: 12px 24px; "
        "text-decoration: none; border-radius: 6px; display: inline-block; font-weight: 600;"
    )
    CODE_STYLE = (
        f"background: #F9FAFC; color: {TEXT_PRIMARY_HEX}; "
        "padding: 6px 10px; border-radius: 4px; font-size: 14px;"
    )

logger = logging.getLogger(__name__)


def _should_skip_email(to_email: str) -> bool:
    """Skip sending in test env or to test domains (Resend sandbox restricts recipients)."""
    if settings.ENVIRONMENT == "test":
        return True
    test_domains = ("@test.com", "@test.example.com", "@resend.dev")
    return any(to_email.lower().endswith(d) for d in test_domains)


def send_email(to_email: str, subject: str, html: str, reply_to: str = None) -> bool:
    """
    Send a single HTML email via Resend. Call this from any service that needs to send mail.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        html: HTML email body
        reply_to: Optional reply-to email address

    Returns True if sent, False if skipped (no API key, test env) or failed.
    """
    if not settings.RESEND_API_KEY:
        logger.info("Email skipped (RESEND_API_KEY not set): to %s, subject=%s", to_email, subject)
        return False
    if _should_skip_email(to_email):
        logger.info("Email skipped (test env or test domain): to %s", to_email)
        return True
    try:
        import resend
        resend.api_key = settings.RESEND_API_KEY
        email_data = {
            "from": settings.EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "html": html,
        }
        if reply_to:
            email_data["reply_to"] = reply_to

        resend.Emails.send(email_data)
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.exception("Failed to send email to %s: %s", to_email, e)
        return False


def send_teacher_invite(to_email: str, first_name: str, access_code: str) -> bool:
    """
    Send teacher invite email with access code and signup link (branded).
    Returns True if sent, False if skipped or failed.
    """
    signup_url = f"{settings.FRONTEND_SIGNUP_URL.rstrip('/')}?{urlencode({'code': access_code})}"
    invite_manual_line = (
        f'<p style="color: {TEXT_MUTED_HEX}; font-size: 14px;">Or copy this code manually: '
        f'<code style="{CODE_STYLE}">{access_code}</code></p>'
    )
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>YouSpeak Teacher Invite</title></head>
<body style="font-family: {FONT_FAMILY}; line-height: 1.6; color: {TEXT_PRIMARY_HEX}; "
      "max-width: 560px; margin: 0 auto; padding: 20px;">
  <h2 style="color: {PRIMARY_HEX};">You've been invited to join YouSpeak</h2>
  <p>Hi {first_name},</p>
  <p>Your school administrator has invited you to join YouSpeak as a teacher.</p>
  <p>Use the link below to create your account:</p>
  <p style="margin: 24px 0;">
    <a href="{signup_url}" style="{BUTTON_STYLE}">Sign up now</a>
  </p>
  {invite_manual_line}
  <p style="color: {TEXT_MUTED_HEX}; font-size: 14px;">This invite expires in 7 days.</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
  <p style="color: #94a3b8; font-size: 12px;">YouSpeak — Language learning platform</p>
</body>
</html>
"""
    return send_email(to_email, "You've been invited to join YouSpeak", html)


def send_password_reset(to_email: str, reset_link: str) -> bool:
    """
    Send password reset email with link (branded). Other services can call send_email
    for custom templates; this is the standard reset flow.
    Returns True if sent, False if skipped or failed.
    """
    reset_expiry_line = (
        f'<p style="color: {TEXT_MUTED_HEX}; font-size: 14px;">This link expires in 1 hour. '
        "If you didn't request a reset, you can ignore this email.</p>"
    )
    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Reset your YouSpeak password</title></head>
<body style="font-family: {FONT_FAMILY}; line-height: 1.6; color: {TEXT_PRIMARY_HEX}; "
      "max-width: 560px; margin: 0 auto; padding: 20px;">
  <h2 style="color: {PRIMARY_HEX};">Reset your password</h2>
  <p>We received a request to reset the password for your YouSpeak account.</p>
  <p>Click the button below to choose a new password:</p>
  <p style="margin: 24px 0;">
    <a href="{reset_link}" style="{BUTTON_STYLE}">Reset password</a>
  </p>
  {reset_expiry_line}
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
  <p style="color: #94a3b8; font-size: 12px;">YouSpeak — Language learning platform</p>
</body>
</html>
"""
    return send_email(to_email, "Reset your YouSpeak password", html)


# --- Bulk Email with Audit Trail ---

import hashlib
from typing import List, Tuple, Dict, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession


def _hash_html_body(html: str) -> str:
    """Hash HTML body for audit trail (SHA256)."""
    return hashlib.sha256(html.encode('utf-8')).hexdigest()


async def send_bulk_email(
    db: AsyncSession,
    sender_id: UUID,
    school_id: Optional[UUID],
    recipients: List[str],
    subject: str,
    html_body: str,
    reply_to: Optional[str] = None,
) -> Tuple[object, Dict[str, Tuple[bool, Optional[str]]]]:
    """
    Send email to multiple recipients and log to database.

    Args:
        db: Database session
        sender_id: UUID of user sending the email
        school_id: UUID of sender's school (nullable)
        recipients: List of recipient email addresses
        subject: Email subject line
        html_body: HTML email content
        reply_to: Optional reply-to email address

    Returns:
        Tuple of (EmailLog object, results dict)
        results dict: {recipient_email: (success: bool, error: Optional[str])}
    """
    from app.models.communication import EmailLog
    from app.models.enums import EmailSendStatus
    from app.utils.time import get_utc_now

    # Create email log entry
    email_log = EmailLog(
        sender_id=sender_id,
        school_id=school_id,
        recipients=recipients,
        subject=subject,
        html_body_sha256=_hash_html_body(html_body),
        send_status=EmailSendStatus.PENDING.value,
    )
    db.add(email_log)
    await db.flush()  # Get ID before sending

    # Send to each recipient
    results: Dict[str, Tuple[bool, Optional[str]]] = {}
    successful = 0
    failed = 0

    for recipient_email in recipients:
        try:
            success = send_email(
                to_email=recipient_email,
                subject=subject,
                html=html_body,
                reply_to=reply_to,
            )
            if success:
                results[recipient_email] = (True, None)
                successful += 1
            else:
                results[recipient_email] = (False, "Email service returned false")
                failed += 1
        except Exception as e:
            logger.exception(f"Failed to send to {recipient_email}")
            results[recipient_email] = (False, str(e))
            failed += 1

    # Update email log status
    if failed == 0:
        email_log.send_status = EmailSendStatus.SENT.value
    elif successful == 0:
        email_log.send_status = EmailSendStatus.FAILED.value
        email_log.error_message = "All recipients failed"
    else:
        email_log.send_status = EmailSendStatus.SENT.value
        email_log.error_message = f"{failed}/{len(recipients)} recipients failed"

    email_log.sent_at = get_utc_now()

    await db.commit()
    await db.refresh(email_log)

    logger.info(
        f"Bulk email sent: {successful} succeeded, {failed} failed",
        extra={
            "sender_id": str(sender_id),
            "recipient_count": len(recipients),
            "successful": successful,
            "failed": failed,
            "email_log_id": str(email_log.id),
        }
    )

    return email_log, results
