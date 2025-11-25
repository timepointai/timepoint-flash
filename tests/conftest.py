"""
Pytest configuration and fixtures for Timepoint Flash tests.
"""
import os
import sys
from typing import AsyncGenerator, Generator
from pathlib import Path
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Base, get_db
from app.main import app
from app.config import Settings

# Load environment variables from .env or .env.dev
load_dotenv()
load_dotenv(".env.dev")


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """
    Create test settings with appropriate environment variables.
    """
    # Ensure OPENROUTER_API_KEY is available
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set - skipping test")

    return Settings(
        DATABASE_URL="sqlite:///:memory:",  # In-memory SQLite for tests
        OPENROUTER_API_KEY=api_key,
        DEBUG=True,
        MAX_TIMEPOINTS_PER_HOUR=100,  # Increase for testing
    )


@pytest.fixture(scope="function")
def db_engine(test_settings: Settings):
    """
    Create a test database engine with in-memory SQLite.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Drop all tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """
    Create a test database session.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_engine
    )

    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(db_session: Session, test_settings: Settings) -> Generator[TestClient, None, None]:
    """
    Create a test client with database session override.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_settings():
        return test_settings

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def openrouter_api_key() -> str:
    """
    Get OpenRouter API key from environment.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set - skipping test")
    return api_key


@pytest.fixture(scope="session")
def google_api_key() -> str:
    """
    Get Google API key from environment (optional).
    """
    return os.getenv("GOOGLE_API_KEY", "")


# Pytest markers for test organization
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "fast: Fast unit tests (no external API calls)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end integration tests (requires API keys)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (long-running operations)"
    )
