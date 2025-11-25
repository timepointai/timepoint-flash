"""
Rate limiting logic to prevent spam.

Enforces: 1 timepoint per hour per email address.
Exception: Unlimited requests from *.replit.dev domains (for development).
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models import Email, RateLimit
from app.config import settings


def check_rate_limit(db: Session, email_address: str, host: str | None = None) -> tuple[bool, str | None]:
    """
    Check if user is allowed to create a new timepoint.

    Args:
        db: Database session
        email_address: Email to check
        host: Request host header (to check for replit.dev)

    Returns:
        (is_allowed, error_message)
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[RATE_LIMIT] Checking rate limit for {email_address}, host: {host}")

    # Bypass rate limiting for replit.dev domains and timepointai.com (during beta)
    if host and (host.endswith('.replit.dev') or host == 'timepointai.com' or host.startswith('timepointai.com')):
        logger.info(f"[RATE_LIMIT] Bypassing rate limit for trusted host: {host}")
        return (True, None)

    # Get email record
    email_obj = db.query(Email).filter(Email.email == email_address).first()

    if not email_obj:
        # First time user, allow
        logger.info(f"[RATE_LIMIT] First time user, allowing: {email_address}")
        return (True, None)

    # Get or create rate limit record
    rate_limit = db.query(RateLimit).filter(RateLimit.email_id == email_obj.id).first()

    if not rate_limit:
        # No rate limit record yet, allow
        logger.info(f"[RATE_LIMIT] No rate limit record found, allowing: {email_address}")
        return (True, None)

    # Check if last creation was within the past hour
    if rate_limit.last_created_at:
        time_since_last = datetime.utcnow() - rate_limit.last_created_at
        logger.info(f"[RATE_LIMIT] Last creation was {time_since_last.total_seconds()} seconds ago")
        if time_since_last < timedelta(hours=1):
            minutes_remaining = 60 - int(time_since_last.total_seconds() / 60)
            logger.warning(f"[RATE_LIMIT] Rate limit exceeded for {email_address}, {minutes_remaining} minutes remaining")
            return (
                False,
                f"Rate limit exceeded. You can create {settings.MAX_TIMEPOINTS_PER_HOUR} timepoint per hour. "
                f"Please wait {minutes_remaining} minutes."
            )

    logger.info(f"[RATE_LIMIT] Rate limit check passed for {email_address}")
    return (True, None)


def update_rate_limit(db: Session, email_address: str):
    """
    Update rate limit after successful timepoint creation.

    Args:
        db: Database session
        email_address: Email address
    """
    email_obj = db.query(Email).filter(Email.email == email_address).first()

    if not email_obj:
        return

    rate_limit = db.query(RateLimit).filter(RateLimit.email_id == email_obj.id).first()

    if not rate_limit:
        # Create new rate limit record
        rate_limit = RateLimit(email_id=email_obj.id, last_created_at=datetime.utcnow(), count_1h=1)
        db.add(rate_limit)
    else:
        # Update existing
        rate_limit.last_created_at = datetime.utcnow()
        rate_limit.count_1h = 1

    db.commit()
