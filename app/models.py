"""SQLAlchemy models for TIMEPOINT Flash.

This module defines the database models for storing timepoints,
their metadata, and relationships.

Examples:
    >>> from app.models import Timepoint, TimepointStatus
    >>> timepoint = Timepoint(
    ...     query="signing of the declaration",
    ...     slug="signing-of-the-declaration-1776",
    ...     status=TimepointStatus.COMPLETED,
    ... )

Tests:
    - tests/unit/test_models.py::test_timepoint_creation
    - tests/unit/test_models.py::test_timepoint_slug_generation
    - tests/unit/test_models.py::test_timepoint_status_transitions
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class."""

    pass


class TimepointStatus(str, Enum):
    """Status of a timepoint generation.

    States:
        PENDING: Queued for generation
        PROCESSING: Currently being generated
        COMPLETED: Successfully generated
        FAILED: Generation failed
    """

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def generate_slug(query: str, year: int | None = None) -> str:
    """Generate URL-safe slug from query.

    Args:
        query: The timepoint query.
        year: Optional year to append.

    Returns:
        URL-safe slug string.

    Examples:
        >>> generate_slug("Signing of the Declaration")
        'signing-of-the-declaration'
        >>> generate_slug("Rome", 50)
        'rome-50'
    """
    # Lowercase and replace spaces
    slug = query.lower().strip()

    # Remove special characters
    slug = re.sub(r"[^\w\s-]", "", slug)

    # Replace spaces with hyphens
    slug = re.sub(r"[-\s]+", "-", slug)

    # Append year if provided
    if year is not None:
        slug = f"{slug}-{year}"

    # Limit length
    return slug[:100]


class Timepoint(Base):
    """Core Timepoint model representing a temporal simulation.

    Attributes:
        id: Unique identifier (UUID)
        query: Original user query
        slug: URL-safe identifier
        status: Current generation status
        year: Temporal year
        month: Temporal month (optional)
        day: Temporal day (optional)
        season: Season (spring, summer, fall, winter)
        time_of_day: Time description (morning, afternoon, etc.)
        location: Geographic location
        metadata_json: Full metadata dictionary
        character_data_json: Character information
        scene_data_json: Scene environment data
        dialog_json: Dialog lines
        image_prompt: Generated image prompt
        image_url: Generated image URL/path
        created_at: Creation timestamp
        updated_at: Last update timestamp
        parent_id: ID of prior timepoint (for sequences)
        error_message: Error details if failed

    Relationships:
        parent: Parent timepoint (prior moment)
        children: Child timepoints (next moments)
    """

    __tablename__ = "timepoints"

    # Primary key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Core fields
    query: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    status: Mapped[TimepointStatus] = mapped_column(
        SQLEnum(TimepointStatus),
        default=TimepointStatus.PENDING,
        index=True,
    )

    # Temporal fields
    year: Mapped[int | None] = mapped_column(default=None, index=True)
    month: Mapped[int | None] = mapped_column(default=None)
    day: Mapped[int | None] = mapped_column(default=None)
    season: Mapped[str | None] = mapped_column(String(20), default=None)
    time_of_day: Mapped[str | None] = mapped_column(String(50), default=None)
    era: Mapped[str | None] = mapped_column(String(50), default=None)

    # Location
    location: Mapped[str | None] = mapped_column(Text, default=None)

    # JSON data fields
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    character_data_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    scene_data_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    dialog_json: Mapped[list[dict[str, str]] | None] = mapped_column(
        JSON,
        default=None,
    )

    # Image generation
    image_prompt: Mapped[str | None] = mapped_column(Text, default=None)
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    image_base64: Mapped[str | None] = mapped_column(Text, default=None)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships for temporal sequences
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("timepoints.id"),
        default=None,
    )
    parent: Mapped["Timepoint | None"] = relationship(
        "Timepoint",
        remote_side=[id],
        back_populates="children",
        foreign_keys=[parent_id],
    )
    children: Mapped[list["Timepoint"]] = relationship(
        "Timepoint",
        back_populates="parent",
        foreign_keys=[parent_id],
    )

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    def __repr__(self) -> str:
        """String representation."""
        status_val = self.status.value if self.status else "None"
        return f"<Timepoint(slug='{self.slug}', status={status_val})>"

    @classmethod
    def create(cls, query: str, **kwargs: Any) -> "Timepoint":
        """Factory method to create a timepoint with slug.

        Args:
            query: The timepoint query.
            **kwargs: Additional fields.

        Returns:
            New Timepoint instance.

        Examples:
            >>> tp = Timepoint.create("Rome 50 BCE")
            >>> tp.slug
            'rome-50-bce'
        """
        year = kwargs.get("year")
        slug = kwargs.pop("slug", None) or generate_slug(query, year)
        # Set default status if not provided
        if "status" not in kwargs:
            kwargs["status"] = TimepointStatus.PENDING
        return cls(query=query, slug=slug, **kwargs)

    def mark_processing(self) -> None:
        """Mark timepoint as processing."""
        self.status = TimepointStatus.PROCESSING

    def mark_completed(self) -> None:
        """Mark timepoint as completed."""
        self.status = TimepointStatus.COMPLETED

    def mark_failed(self, error: str) -> None:
        """Mark timepoint as failed with error message.

        Args:
            error: The error message.
        """
        self.status = TimepointStatus.FAILED
        self.error_message = error

    @property
    def is_complete(self) -> bool:
        """Check if timepoint generation is complete."""
        return self.status == TimepointStatus.COMPLETED

    @property
    def has_image(self) -> bool:
        """Check if timepoint has generated image."""
        return self.image_url is not None or self.image_base64 is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses.

        Returns:
            Dictionary representation.
        """
        return {
            "id": self.id,
            "query": self.query,
            "slug": self.slug,
            "status": self.status.value if self.status else None,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "season": self.season,
            "time_of_day": self.time_of_day,
            "era": self.era,
            "location": self.location,
            "metadata": self.metadata_json,
            "characters": self.character_data_json,
            "scene": self.scene_data_json,
            "dialog": self.dialog_json,
            "image_prompt": self.image_prompt,
            "image_url": self.image_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "parent_id": self.parent_id,
            "error": self.error_message,
        }


class GenerationLog(Base):
    """Log of generation steps for debugging and monitoring.

    Tracks each step of the timepoint generation workflow.

    Attributes:
        id: Unique identifier
        timepoint_id: Associated timepoint
        step: Step name (e.g., "judge", "timeline", "scene")
        status: Step status
        input_data: Input to the step
        output_data: Output from the step
        model_used: LLM model used
        provider: Provider used (google/openrouter)
        latency_ms: Step latency
        token_usage: Token usage statistics
        error_message: Error if step failed
        created_at: Timestamp
    """

    __tablename__ = "generation_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    timepoint_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("timepoints.id"),
        index=True,
    )
    step: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20))
    input_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    model_used: Mapped[str | None] = mapped_column(String(100), default=None)
    provider: Mapped[str | None] = mapped_column(String(20), default=None)
    latency_ms: Mapped[int | None] = mapped_column(default=None)
    token_usage: Mapped[dict[str, int] | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<GenerationLog(step='{self.step}', status='{self.status}')>"
