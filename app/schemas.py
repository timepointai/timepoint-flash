"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class ProcessingStatus(str, Enum):
    """Status of timepoint processing."""
    PENDING = "pending"
    VALIDATING = "validating"
    GENERATING_SCENE = "generating_scene"
    GENERATING_IMAGE = "generating_image"
    SEGMENTING = "segmenting"
    COMPLETED = "completed"
    FAILED = "failed"


class CharacterPosition(BaseModel):
    """3D position and orientation for a character."""
    x: float = Field(..., ge=0.0, le=1.0, description="X coordinate (0-1)")
    y: float = Field(..., ge=0.0, le=1.0, description="Y coordinate (0-1)")
    z: float = Field(..., ge=0.0, le=1.0, description="Z depth (0-1)")
    orientation: str = Field(default="facing center", description="Direction facing (e.g., 'facing center', 'profile left')")


class Character(BaseModel):
    """Character definition for scene generation (max 1K tokens)."""
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "name": "Benjamin Franklin",
            "role": "Founding Father, Diplomat",
            "appearance": "Elderly man, balding with long gray hair, round spectacles",
            "clothing": "18th century colonial formal attire, brown coat, white cravat",
            "position": {"x": 0.3, "y": 0.5, "z": 0, "orientation": "facing center"},
            "expression": "Thoughtful, slight smile",
            "body_language": "Leaning forward, engaged in discussion",
            "key_prop": "Quill pen",
            "bio": "Renowned polymath, one of the key architects of American independence"
        }
    })

    name: str = Field(..., max_length=50)
    role: str = Field(..., max_length=100)
    appearance: str = Field(..., max_length=300, description="Physical description")
    clothing: str = Field(..., max_length=200, description="Period-accurate attire")
    position: CharacterPosition
    expression: str = Field(..., max_length=100)
    body_language: str = Field(..., max_length=100)
    key_prop: Optional[str] = Field(None, max_length=100)
    bio: str = Field(..., max_length=500, description="Background context")


class TimepointCreateRequest(BaseModel):
    """Request to create a new timepoint."""
    email: EmailStr
    query: str = Field(..., min_length=5, max_length=500, description="Time period or event description")


class TimepointCreateResponse(BaseModel):
    """Response after initiating timepoint creation."""
    session_id: str
    status: ProcessingStatus
    message: str


class TimepointStatusResponse(BaseModel):
    """Current status of timepoint processing."""
    session_id: str
    status: ProcessingStatus
    progress: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timepoint_id: Optional[UUID] = None


class TimepointResponse(BaseModel):
    """Complete timepoint data."""
    id: UUID
    slug: str
    year: int
    season: str
    input_query: str
    cleaned_query: str
    scene_graph: Optional[Dict[str, Any]] = None
    characters: Optional[List[Character]] = None
    dialog: Optional[List[Dict[str, str]]] = None
    metadata: Optional[Dict[str, Any]] = None
    image_url: Optional[str] = None
    segmented_image_url: Optional[str] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime


class FeedResponse(BaseModel):
    """Paginated feed of recent timepoints."""
    timepoints: List[TimepointResponse]
    total: int
    page: int
    per_page: int
    has_more: bool


class EmailVerifyRequest(BaseModel):
    """Request to verify email."""
    token: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    service: str
