"""Pydantic schemas for auth and credits API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AppleSignInRequest(BaseModel):
    """Request body for Apple Sign-In."""

    identity_token: str = Field(
        ..., description="Apple identity JWT from ASAuthorizationAppleIDCredential"
    )


class TokenResponse(BaseModel):
    """JWT token pair returned on sign-in or refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


class LogoutRequest(BaseModel):
    """Request body for logout (revoke refresh token)."""

    refresh_token: str


class UserResponse(BaseModel):
    """Public user profile."""

    id: str
    email: str | None = None
    display_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditBalanceResponse(BaseModel):
    """Current credit balance."""

    balance: int
    lifetime_earned: int
    lifetime_spent: int


class CreditTransactionResponse(BaseModel):
    """Single credit ledger entry."""

    amount: int
    balance_after: int
    type: str
    description: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditCostsResponse(BaseModel):
    """Maps operation names to credit costs."""

    costs: dict[str, int]


class DevTokenRequest(BaseModel):
    """Request body for dev token creation."""

    email: str = Field(..., description="Email for the test user")
    display_name: str | None = Field(
        default=None, description="Optional display name"
    )


class AdminGrantRequest(BaseModel):
    """Request body for admin credit grant."""

    user_id: str = Field(..., description="Target user UUID")
    amount: int = Field(..., gt=0, description="Credits to grant")
    transaction_type: str | None = Field(
        default=None,
        description="Ledger transaction type (e.g. stripe_purchase, apple_iap). Defaults to admin_grant.",
    )
    description: str | None = Field(
        default="Manual top-up", description="Ledger note"
    )


class AdminGrantResponse(BaseModel):
    """Response for admin credit grant."""

    balance: int
    granted: int
