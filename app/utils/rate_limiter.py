"""
Rate limiting logic to prevent spam.

Enforces:
- Email-based: 1 timepoint per hour per email address
- IP-based: 10 timepoints per hour for anonymous requests (no email)
- Trusted hosts: Unlimited (*.replit.dev, timepointai.com)
"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.models import Email, RateLimit, IPRateLimit
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


def check_ip_rate_limit(db: Session, ip_address: str, host: str | None = None) -> tuple[bool, str | None]:
    """
    Check IP-based rate limit for anonymous/public API access.

    Args:
        db: Database session
        ip_address: IP address to check
        host: Request host header (to check for trusted domains)

    Returns:
        (is_allowed, error_message)
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[IP_RATE_LIMIT] Checking IP rate limit for {ip_address}, host: {host}")

    # Bypass rate limiting for trusted domains
    if host and (host.endswith('.replit.dev') or host == 'timepointai.com' or host.startswith('timepointai.com')):
        logger.info(f"[IP_RATE_LIMIT] Bypassing IP rate limit for trusted host: {host}")
        return (True, None)

    # Get or create IP rate limit record
    ip_rate_limit = db.query(IPRateLimit).filter(IPRateLimit.ip_address == ip_address).first()

    if not ip_rate_limit:
        # First time seeing this IP, allow
        logger.info(f"[IP_RATE_LIMIT] First time IP, allowing: {ip_address}")
        return (True, None)

    # Check if last creation was within the past hour
    if ip_rate_limit.last_created_at:
        time_since_last = datetime.utcnow() - ip_rate_limit.last_created_at
        logger.info(f"[IP_RATE_LIMIT] Last creation was {time_since_last.total_seconds()} seconds ago")

        # Reset counter if it's been more than an hour
        if time_since_last >= timedelta(hours=1):
            ip_rate_limit.count_1h = 0
            ip_rate_limit.last_created_at = None
            db.commit()
            logger.info(f"[IP_RATE_LIMIT] Counter reset for IP: {ip_address}")
            return (True, None)

        # Check if under the limit (10 per hour for anonymous)
        if ip_rate_limit.count_1h >= 10:
            minutes_remaining = 60 - int(time_since_last.total_seconds() / 60)
            logger.warning(f"[IP_RATE_LIMIT] IP rate limit exceeded for {ip_address}, {minutes_remaining} minutes remaining")
            return (
                False,
                f"Rate limit exceeded. Anonymous users can create 10 timepoints per hour. "
                f"Please wait {minutes_remaining} minutes or provide an email address."
            )

    logger.info(f"[IP_RATE_LIMIT] IP rate limit check passed for {ip_address} (count: {ip_rate_limit.count_1h}/10)")
    return (True, None)


def update_ip_rate_limit(db: Session, ip_address: str):
    """
    Update IP rate limit after successful timepoint creation.

    Args:
        db: Database session
        ip_address: IP address
    """
    ip_rate_limit = db.query(IPRateLimit).filter(IPRateLimit.ip_address == ip_address).first()

    if not ip_rate_limit:
        # Create new IP rate limit record
        ip_rate_limit = IPRateLimit(
            ip_address=ip_address,
            last_created_at=datetime.utcnow(),
            count_1h=1
        )
        db.add(ip_rate_limit)
    else:
        # Check if we need to reset the counter (>1 hour since last request)
        if ip_rate_limit.last_created_at:
            time_since_last = datetime.utcnow() - ip_rate_limit.last_created_at
            if time_since_last >= timedelta(hours=1):
                # Reset counter
                ip_rate_limit.count_1h = 1
            else:
                # Increment counter
                ip_rate_limit.count_1h += 1
        else:
            ip_rate_limit.count_1h = 1

        ip_rate_limit.last_created_at = datetime.utcnow()

    db.commit()
