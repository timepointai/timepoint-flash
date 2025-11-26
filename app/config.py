"""
Application configuration using Pydantic BaseSettings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Reads from both .env file (for local dev) and environment variables (for Replit deployment).
    Environment variables take precedence over .env file values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables
    )

    # Application
    DEBUG: bool = False
    SITE_NAME: str = "TIMEPOINT AI"
    BASE_URL: str = "http://localhost:5000"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5000", "http://localhost:3000", "http://localhost:4321"]

    # Database
    DATABASE_URL: str

    # Google AI Suite
    GOOGLE_API_KEY: str
    
    # Models
    # Using Gemini 1.5 Flash for fast logic/judging
    JUDGE_MODEL: str = "gemini-1.5-flash"
    # Using Gemini 1.5 Pro for complex creative generation (scenes, dialog)
    CREATIVE_MODEL: str = "gemini-1.5-pro"

    # Image Generation: Nano Banana Models 🍌
    # RECOMMENDED: Nano Banana (Gemini 2.5 Flash Image)
    # - $0.039/image, 1024x1024px, best price/quality
    # ADVANCED: Nano Banana Pro (Gemini 3 Pro Image) - NEW!
    # - $0.139-0.24/image, 2K/4K, text rendering, advanced controls
    # - Use: google/gemini-3-pro-image-preview
    IMAGE_MODEL: str = "google/gemini-2.5-flash-image"

    # Budget/Testing Mode - Use free preview model
    USE_FREE_MODELS: bool = False  # Set to True to use free preview models

    # OpenRouter API (Legacy/Backup)
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Replit Object Storage
    REPLIT_OBJECT_STORAGE_URL: str | None = None

    # Logfire (observability)
    LOGFIRE_TOKEN: str | None = None

    # Rate Limiting
    MAX_TIMEPOINTS_PER_HOUR: int = 5
    SESSION_EXPIRY_MINUTES: int = 60

    # Email
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    FROM_EMAIL: str = "noreply@timepoint.ai"

    # Security
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30


settings = Settings()
