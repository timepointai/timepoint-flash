"""
SQLAlchemy ORM models for database tables.
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, DateTime, Enum, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum

from app.database import Base


class ProcessingStatus(str, enum.Enum):
    """Status of timepoint processing."""
    PENDING = "pending"
    VALIDATING = "validating"
    GENERATING_SCENE = "generating_scene"
    GENERATING_IMAGE = "generating_image"
    SEGMENTING = "segmenting"
    COMPLETED = "completed"
    FAILED = "failed"


class Email(Base):
    """Email addresses for user identification and rate limiting."""
    __tablename__ = "emails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())
    verified = Column(Boolean, default=False)
    verification_token = Column(String(255), nullable=True)

    # Relationships
    timepoints = relationship("Timepoint", back_populates="email_obj")
    rate_limit = relationship("RateLimit", back_populates="email_obj", uselist=False)


class Timepoint(Base):
    """Generated timepoint with scene, characters, and images."""
    __tablename__ = "timepoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), nullable=False)

    # Permalink components
    slug = Column(String(255), unique=True, index=True, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String(50), nullable=False)

    # Input and processing
    input_query = Column(Text, nullable=False)
    cleaned_query = Column(Text, nullable=False)
    is_fictional = Column(Boolean, default=False, nullable=False)  # For fictional timelines (Star Wars, LOTR, etc)

    # Scene data
    scene_graph_json = Column(JSONB, nullable=True)
    character_data_json = Column(JSONB, nullable=True)
    dialog_json = Column(JSONB, nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    # Images (using Text to support large base64 data URLs)
    image_url = Column(Text, nullable=True)
    segmented_image_url = Column(Text, nullable=True)

    # Metrics
    processing_time_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    email_obj = relationship("Email", back_populates="timepoints")


class RateLimit(Base):
    """Rate limiting per email address."""
    __tablename__ = "rate_limits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_id = Column(UUID(as_uuid=True), ForeignKey("emails.id"), unique=True, nullable=False)

    last_created_at = Column(TIMESTAMP, nullable=True)
    count_1h = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    email_obj = relationship("Email", back_populates="rate_limit")


class ProcessingSession(Base):
    """Temporary session data for ongoing timepoint generation."""
    __tablename__ = "processing_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=False)

    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    progress_data_json = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    timepoint_id = Column(UUID(as_uuid=True), ForeignKey("timepoints.id"), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    expires_at = Column(TIMESTAMP, nullable=False)
