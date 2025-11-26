"""
SQLAlchemy ORM models for database tables.

Supports both SQLite (local/demo) and PostgreSQL (production).
"""
from sqlalchemy import Column, String, Integer, Boolean, Text, ForeignKey, DateTime, Enum, TIMESTAMP, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid as uuid_module
import enum

from app.database import Base


class UUID(TypeDecorator):
    """Platform-independent UUID type.

    Uses PostgreSQL's UUID type when available, otherwise uses String(36).
    """
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid_module.UUID):
                return str(value)
            return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid_module.UUID):
            return uuid_module.UUID(value)
        return value


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

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
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

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    email_id = Column(UUID(), ForeignKey("emails.id"), nullable=False)

    # Permalink components
    slug = Column(String(255), unique=True, index=True, nullable=False)
    year = Column(Integer, nullable=False)
    season = Column(String(50), nullable=False)

    # Input and processing
    input_query = Column(Text, nullable=False)
    cleaned_query = Column(Text, nullable=False)
    is_fictional = Column(Boolean, default=False, nullable=False)  # For fictional timelines (Star Wars, LOTR, etc)

    # Scene data
    scene_graph_json = Column(JSON, nullable=True)
    character_data_json = Column(JSON, nullable=True)
    dialog_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

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

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    email_id = Column(UUID(), ForeignKey("emails.id"), unique=True, nullable=False)

    last_created_at = Column(TIMESTAMP, nullable=True)
    count_1h = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    email_obj = relationship("Email", back_populates="rate_limit")


class IPRateLimit(Base):
    """Rate limiting per IP address (for anonymous/public API access)."""
    __tablename__ = "ip_rate_limits"

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    ip_address = Column(String(45), unique=True, index=True, nullable=False)  # IPv6 max length is 45

    last_created_at = Column(TIMESTAMP, nullable=True)
    count_1h = Column(Integer, default=0)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())


class ProcessingSession(Base):
    """Temporary session data for ongoing timepoint generation."""
    __tablename__ = "processing_sessions"

    id = Column(UUID(), primary_key=True, default=uuid_module.uuid4)
    session_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), nullable=False)

    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    progress_data_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    timepoint_id = Column(UUID(), ForeignKey("timepoints.id"), nullable=True)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    expires_at = Column(TIMESTAMP, nullable=False)
