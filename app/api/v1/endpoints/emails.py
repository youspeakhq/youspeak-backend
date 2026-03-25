"""Email sending endpoint"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.communication import SendEmailRequest, SendEmailResponse, EmailSendResult
from app.schemas.responses import SuccessResponse
from app.services.email_service import send_bulk_email
from app.core.rate_limit import user_limiter
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


def get_email_rate_limit_by_key(key: str) -> str:
    """
    Dynamic rate limit based on user role from key.

    Key format: "user_id:role" for authenticated users, or IP address for unauthenticated.

    Rate limits:
    - Students: 3 emails per hour
    - Teachers: 10 emails per hour
    - School Admins: 50 emails per hour (higher for administrative tasks)
    - Unauthenticated/Unknown: 3 emails per hour (most restrictive)

    Note: This function receives the key from slowapi's key_func (get_user_key_with_role).
    The role is extracted from the JWT token without additional database queries.
    """
    try:
        # Check if key contains role (format: "user_id:role")
        if ":" not in key:
            # IP-based key (unauthenticated), use most restrictive limit
            return "3/hour"

        # Extract role from key
        _, role = key.rsplit(":", 1)

        # Return rate limit based on role
        if role == UserRole.SCHOOL_ADMIN.value:
            return "50/hour"  # Admins get higher limit for administrative tasks
        elif role == UserRole.TEACHER.value:
            return "10/hour"  # Teachers need moderate limits for class communications
        elif role == UserRole.STUDENT.value:
            return "3/hour"  # Students get lowest limit to prevent spam
        else:
            # Unknown role, use most restrictive
            return "3/hour"

    except Exception as e:
        logger.warning(f"Failed to parse rate limit key: {e}")
        return "3/hour"  # Default to most restrictive on error


@router.post("/send", response_model=SuccessResponse[SendEmailResponse])
@user_limiter.limit(get_email_rate_limit_by_key)  # Dynamic rate limit based on user role
async def send_email_endpoint(
    request: Request,
    email_request: SendEmailRequest,
    current_user: User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(deps.get_db),
):
    """
    Send email to arbitrary recipients.

    Any authenticated user can send emails. Frontend controls all HTML/CSS styling.
    Backend handles delivery via Resend and logs to database for audit.

    **Rate limits (per hour):**
    - Students: 3 emails
    - Teachers: 10 emails
    - Admins: 50 emails

    **Max recipients:** 10 per request
    **Max HTML size:** 500KB
    **Max subject length:** 200 characters
    """
    try:
        # Send emails via bulk service
        email_log, results = await send_bulk_email(
            db=db,
            sender_id=current_user.id,
            school_id=current_user.school_id if hasattr(current_user, 'school_id') else None,
            recipients=email_request.recipients,
            subject=email_request.subject,
            html_body=email_request.html_body,
            reply_to=email_request.reply_to,
        )
    except Exception as e:
        logger.exception("Failed to send bulk email")
        raise HTTPException(status_code=500, detail="Failed to send emails")

    # Build response with per-recipient status
    successful = sum(1 for success, _ in results.values() if success)
    failed = len(results) - successful

    result_list = [
        EmailSendResult(
            recipient=email,
            status="sent" if success else "failed",
            error=error,
        )
        for email, (success, error) in results.items()
    ]

    return SuccessResponse(
        data=SendEmailResponse(
            total_recipients=len(email_request.recipients),
            successful_sends=successful,
            failed_sends=failed,
            results=result_list,
            email_log_id=email_log.id,
        ),
        message=f"Email sent to {successful}/{len(email_request.recipients)} recipients"
    )
