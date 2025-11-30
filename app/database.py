"""Database connection and session management.

This module provides async SQLAlchemy setup for SQLite (dev) and PostgreSQL (prod).
Uses SQLAlchemy 2.0 async patterns with contextmanager sessions.

Examples:
    >>> from app.database import get_session, init_db
    >>> await init_db()  # Create tables
    >>> async with get_session() as session:
    ...     result = await session.execute(select(Timepoint))

Tests:
    - tests/unit/test_database.py::test_get_engine
    - tests/unit/test_database.py::test_session_context
    - tests/integration/test_database.py::test_database_operations
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global engine and session factory (initialized lazily)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create async database engine.

    Returns:
        AsyncEngine: SQLAlchemy async engine.

    Note:
        For SQLite, enables WAL mode and foreign keys.
        For PostgreSQL, configures connection pooling.
    """
    global _engine

    if _engine is None:
        settings = get_settings()

        # Engine configuration varies by database type
        if settings.is_sqlite:
            # SQLite configuration
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                connect_args={"check_same_thread": False},
            )

            # Enable SQLite optimizations
            @event.listens_for(_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.execute("PRAGMA busy_timeout=5000")
                cursor.close()

        else:
            # PostgreSQL configuration
            _engine = create_async_engine(
                settings.DATABASE_URL,
                echo=settings.DEBUG,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
            )

        logger.info(f"Database engine created: {settings.DATABASE_URL.split('@')[-1]}")

    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create async session factory.

    Returns:
        async_sessionmaker: Session factory for creating sessions.
    """
    global _async_session_factory

    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    return _async_session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session as async context manager.

    Yields:
        AsyncSession: Database session.

    Examples:
        >>> async with get_session() as session:
        ...     await session.execute(select(Timepoint))
        ...     await session.commit()

    Note:
        Session is automatically committed on success, rolled back on error.
    """
    factory = get_session_factory()
    session = factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database - create all tables.

    Should be called once at application startup.

    Examples:
        >>> await init_db()
    """
    from app.models import Base

    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Database tables created")


async def drop_db() -> None:
    """Drop all database tables.

    Warning:
        This is destructive! Only use in testing or development.

    Examples:
        >>> await drop_db()  # Careful!
    """
    from app.models import Base

    engine = get_engine()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.warning("Database tables dropped")


async def check_db_connection() -> bool:
    """Check if database is accessible.

    Returns:
        bool: True if database is healthy.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


async def close_db() -> None:
    """Close database connections.

    Should be called at application shutdown.
    """
    global _engine, _async_session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connections closed")


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session.

    Examples:
        >>> @app.get("/items")
        ... async def get_items(session: AsyncSession = Depends(get_db_session)):
        ...     result = await session.execute(select(Item))
        ...     return result.scalars().all()
    """
    async with get_session() as session:
        yield session
