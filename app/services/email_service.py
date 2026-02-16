"""Email service for transactional emails (Resend).

To send to any recipient, verify a domain at resend.com/domains and set
EMAIL_FROM to an address at that domain. See docs/EMAIL_SETUP.md.
"""

import logging
from urllib.parse import urlencode

from app.config import settings

logger = logging.getLogger(__name__)


def _should_skip_email(to_email: str) -> bool:
    """Skip sending in test env or to test domains (Resend sandbox restricts recipients)."""
    if settings.ENVIRONMENT == "test":
        return True
    test_domains = ("@test.com", "@test.example.com", "@resend.dev")
    return any(to_email.lower().endswith(d) for d in test_domains)


def send_teacher_invite(to_email: str, first_name: str, access_code: str) -> bool:
    """
    Send teacher invite email with access code and signup link.
    Uses Resend default domain (onboarding@resend.dev) when no custom domain verified.
    Returns True if sent, False if skipped (no API key, test env) or failed.
    """
    if not settings.RESEND_API_KEY:
        logger.info(
            "Email skipped (RESEND_API_KEY not set): teacher invite to %s, code=%s",
            to_email,
            access_code,
        )
        return False
    if _should_skip_email(to_email):
        logger.info(
            "Email skipped (test env or test domain): teacher invite to %s, code=%s",
            to_email,
            access_code,
        )
        return True

    signup_url = f"{settings.FRONTEND_SIGNUP_URL.rstrip('/')}?{urlencode({'code': access_code})}"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>YouSpeak Teacher Invite</title></head>
<body style="font-family: sans-serif; line-height: 1.6; color: #333; max-width: 560px; margin: 0 auto; padding: 20px;">
  <h2 style="color: #4f46e5;">You've been invited to join YouSpeak</h2>
  <p>Hi {first_name},</p>
  <p>Your school administrator has invited you to join YouSpeak as a teacher.</p>
  <p>Use the link below to create your account:</p>
  <p style="margin: 24px 0;">
    <a href="{signup_url}" style="background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Sign up now</a>
  </p>
  <p style="color: #666; font-size: 14px;">Or copy this code manually: <code style="background: #f1f5f9; padding: 4px 8px; border-radius: 4px;">{access_code}</code></p>
  <p style="color: #666; font-size: 14px;">This invite expires in 7 days.</p>
  <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;">
  <p style="color: #94a3b8; font-size: 12px;">YouSpeak — Language learning platform</p>
</body>
</html>
"""

    try:
        import resend

        resend.api_key = settings.RESEND_API_KEY
        resend.Emails.send(
            {
                "from": settings.EMAIL_FROM,
                "to": [to_email],
                "subject": "You've been invited to join YouSpeak",
                "html": html,
            }
        )
        logger.info("Teacher invite email sent to %s", to_email)
        return True
    except Exception as e:
        logger.exception("Failed to send teacher invite email to %s: %s", to_email, e)
        return False
