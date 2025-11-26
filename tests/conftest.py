"""
Pytest configuration and fixtures for Timepoint Flash tests.

Supports both SQLite (auto-deployed) and PostgreSQL (when configured).
Tests automatically adapt to the available database.
"""
import os
import sys
from typing import AsyncGenerator, Generator, Literal
from pathlib import Path
import pytest
import logging
from sqlalchemy import create_engine, event, text
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

logger = logging.getLogger(__name__)


# ============================================
# Database Detection & Utilities
# ============================================

def detect_database_type(url: str) -> Literal["sqlite", "postgresql", "unknown"]:
    """Detect database type from connection URL."""
    if url.startswith("sqlite"):
        return "sqlite"
    elif url.startswith("postgresql"):
        return "postgresql"
    return "unknown"


def is_postgres_available(url: str) -> bool:
    """Test if PostgreSQL database is reachable.

    Returns:
        True if connection successful, False otherwise
    """
    if not url.startswith("postgresql"):
        return False

    try:
        engine = create_engine(url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        logger.info(f"✓ PostgreSQL connection successful: {url}")
        return True
    except Exception as e:
        logger.warning(f"✗ PostgreSQL unavailable ({url}): {e}")
        return False


def get_test_database_url() -> tuple[str, Literal["sqlite", "postgresql"]]:
    """Get the appropriate database URL for testing.

    Logic:
    1. Check DATABASE_URL environment variable
    2. If PostgreSQL: test connection, fallback to SQLite if unavailable
    3. If SQLite: use as-is
    4. Default: in-memory SQLite

    Returns:
        Tuple of (database_url, database_type)
    """
    env_db_url = os.getenv("DATABASE_URL")

    if not env_db_url:
        logger.info("No DATABASE_URL set, using in-memory SQLite for tests")
        return "sqlite:///:memory:", "sqlite"

    db_type = detect_database_type(env_db_url)

    if db_type == "sqlite":
        logger.info(f"Using SQLite for tests: {env_db_url}")
        return env_db_url, "sqlite"

    elif db_type == "postgresql":
        if is_postgres_available(env_db_url):
            logger.info(f"Using PostgreSQL for tests: {env_db_url}")
            return env_db_url, "postgresql"
        else:
            logger.warning(
                f"PostgreSQL configured but unavailable, falling back to in-memory SQLite. "
                f"To use PostgreSQL, ensure database is running and accessible."
            )
            return "sqlite:///:memory:", "sqlite"

    else:
        logger.warning(f"Unknown database type in URL: {env_db_url}, using in-memory SQLite")
        return "sqlite:///:memory:", "sqlite"


# ============================================
# Test Fixtures
# ============================================

@pytest.fixture(scope="session")
def db_type() -> Literal["sqlite", "postgresql"]:
    """Get the database type being used for tests."""
    _, db_type = get_test_database_url()
    return db_type


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Get the database URL for tests."""
    url, _ = get_test_database_url()
    return url


@pytest.fixture(scope="session")
def test_settings(test_database_url: str) -> Settings:
    """
    Create test settings with appropriate environment variables.
    Uses detected database URL (SQLite or PostgreSQL).
    """
    # Ensure OPENROUTER_API_KEY is available
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        pytest.skip("OPENROUTER_API_KEY not set - skipping test")

    return Settings(
        DATABASE_URL=test_database_url,
        OPENROUTER_API_KEY=api_key,
        GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY", "placeholder"),
        DEBUG=True,
        MAX_TIMEPOINTS_PER_HOUR=100,  # Increase for testing
    )


@pytest.fixture(scope="function")
def db_engine(test_database_url: str, db_type: Literal["sqlite", "postgresql"]):
    """
    Create a test database engine.
    Supports both SQLite and PostgreSQL based on configuration.
    """
    if db_type == "sqlite":
        # SQLite configuration
        if test_database_url == "sqlite:///:memory:":
            # In-memory: use StaticPool to share connection
            engine = create_engine(
                test_database_url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            # File-based: regular pool
            engine = create_engine(
                test_database_url,
                connect_args={"check_same_thread": False},
            )
    else:
        # PostgreSQL configuration
        engine = create_engine(
            test_database_url,
            pool_pre_ping=True,  # Verify connections before using
        )

    # Create all tables
    Base.metadata.create_all(bind=engine)

    yield engine

    # Cleanup
    if db_type == "sqlite" and test_database_url != "sqlite:///:memory:":
        # Drop tables for file-based SQLite
        Base.metadata.drop_all(bind=engine)
    elif db_type == "postgresql":
        # Drop tables for PostgreSQL
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


# ============================================
# Pytest Configuration
# ============================================

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
    config.addinivalue_line(
        "markers", "postgres: Tests that require PostgreSQL (auto-skip if unavailable)"
    )
    config.addinivalue_line(
        "markers", "sqlite: Tests specific to SQLite behavior"
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip postgres tests if PostgreSQL is not available."""
    db_url, db_type = get_test_database_url()

    if db_type != "postgresql":
        skip_postgres = pytest.mark.skip(reason="PostgreSQL not available, using SQLite")
        for item in items:
            if "postgres" in item.keywords:
                item.add_marker(skip_postgres)
