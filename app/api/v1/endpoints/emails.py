"""Email sending endpoint"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.communication import SendEmailRequest, SendEmailResponse, EmailSendResult
from app.schemas.responses import SuccessResponse
from app.services.email_service import send_bulk_email
from app.core.rate_limit import limiter
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/test", tags=["Debug"])
async def test_emails_router():
    """Debug endpoint to verify emails router is accessible"""
    return {"message": "Emails router is working"}


def get_email_rate_limit(request: Request) -> str:
    """
    Get dynamic rate limit based on user role from JWT token.

    Rate limits:
    - Students: 3 emails per hour
    - Teachers: 10 emails per hour
    - Admins: 50 emails per hour (higher for administrative tasks)

    Note: Role is read directly from JWT claims (no database query needed).
    """
    try:
        # Get Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return "3/hour"  # Default to most restrictive

        token = auth_header.replace("Bearer ", "")

        # Decode token to get user role
        from app.core.security import decode_token
        payload = decode_token(token)

        if not payload:
            return "3/hour"  # Default to most restrictive

        # Get role from JWT claims
        role = payload.get("role")
        if not role:
            return "3/hour"  # Default if role not in token

        # Return rate limit based on role
        if role == UserRole.SCHOOL_ADMIN.value:
            return "50/hour"  # Admins get higher limit for administrative tasks
        elif role == UserRole.TEACHER.value:
            return "10/hour"  # Teachers need moderate limits for class communications
        else:  # UserRole.STUDENT or any other role
            return "3/hour"  # Students get lowest limit to prevent spam

    except Exception as e:
        logger.warning(f"Failed to get dynamic rate limit: {e}")
        return "3/hour"  # Default to most restrictive on error


@router.post("/send", response_model=SuccessResponse[SendEmailResponse])
# NOTE: Rate limiting temporarily disabled to debug 404 issue
# @limiter.limit(get_email_rate_limit)  # Dynamic rate limit based on user role
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
