"""
Email verification endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import EmailVerifyRequest
from app.models import Email

router = APIRouter()


@router.post("/verify/{token}")
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify email address with token."""
    email = db.query(Email).filter(Email.verification_token == token).first()

    if not email:
        raise HTTPException(status_code=404, detail="Invalid or expired verification token")

    email.verified = True
    email.verification_token = None
    db.commit()

    return {"message": "Email verified successfully"}


@router.post("/resend")
async def resend_verification(email_address: str, db: Session = Depends(get_db)):
    """Resend verification email."""
    # TODO: Implement email sending
    raise HTTPException(status_code=501, detail="Not implemented yet")
