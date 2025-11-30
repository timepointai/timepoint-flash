"""Scene step schema for environment generation.

The Scene step creates the physical environment, atmosphere,
and sensory details of the temporal moment.

Examples:
    >>> from app.schemas.scene import SceneData, SensoryDetail
    >>> scene = SceneData(
    ...     setting="The Assembly Room of Independence Hall",
    ...     atmosphere="Tense anticipation mixed with humid summer air",
    ...     weather="Hot and humid July afternoon",
    ...     lighting="Natural light through tall windows"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_scene_data_valid
    - tests/unit/test_schemas.py::test_sensory_detail
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SensoryDetail(BaseModel):
    """A single sensory detail for the scene.

    Attributes:
        sense: The sense type (sight, sound, smell, touch, taste)
        description: The sensory description
        intensity: How prominent (subtle, moderate, prominent)
    """

    sense: str = Field(..., description="Type of sense (sight, sound, smell, etc.)")
    description: str = Field(..., description="The sensory description")
    intensity: str = Field(
        default="moderate",
        description="Intensity level (subtle, moderate, prominent)",
    )


class SceneData(BaseModel):
    """Environment and atmosphere data for the scene.

    Attributes:
        setting: The physical location description
        atmosphere: Emotional/social atmosphere
        weather: Weather conditions
        lighting: Lighting conditions
        architecture: Architectural style and details
        objects: Notable objects in the scene
        sensory_details: List of sensory experiences
        crowd_description: Description of any crowd/audience
        tension_level: Dramatic tension (low, medium, high, climactic)

    Examples:
        >>> scene = SceneData(
        ...     setting="Independence Hall's Assembly Room",
        ...     atmosphere="Historic gravity, nervous energy",
        ...     weather="Hot summer day",
        ...     lighting="Afternoon light through windows"
        ... )
    """

    # Core environment
    setting: str = Field(
        ...,
        description="Physical location and immediate surroundings",
    )
    atmosphere: str = Field(
        ...,
        description="Emotional and social atmosphere",
    )

    # Environmental conditions
    weather: str | None = Field(
        default=None,
        description="Weather conditions",
    )
    lighting: str | None = Field(
        default=None,
        description="Lighting conditions and quality",
    )
    temperature: str | None = Field(
        default=None,
        description="Temperature description",
    )

    # Physical details
    architecture: str | None = Field(
        default=None,
        description="Architectural style and notable features",
    )
    objects: list[str] = Field(
        default_factory=list,
        description="Notable objects in the scene",
    )
    furniture: list[str] = Field(
        default_factory=list,
        description="Furniture and fixtures",
    )

    # Sensory experience
    sensory_details: list[SensoryDetail] = Field(
        default_factory=list,
        description="Detailed sensory experiences",
    )

    # Social context
    crowd_description: str | None = Field(
        default=None,
        description="Description of crowd or audience if present",
    )
    social_dynamics: str | None = Field(
        default=None,
        description="Social relationships and dynamics in the scene",
    )

    # Dramatic elements
    tension_level: str = Field(
        default="medium",
        description="Dramatic tension level (low, medium, high, climactic)",
    )
    mood: str | None = Field(
        default=None,
        description="Overall mood of the scene",
    )

    # Visual composition hints
    focal_point: str | None = Field(
        default=None,
        description="Primary visual focal point",
    )
    color_palette: list[str] = Field(
        default_factory=list,
        description="Dominant colors in the scene",
    )

    def get_sensory_by_type(self, sense_type: str) -> list[SensoryDetail]:
        """Get all sensory details of a specific type."""
        return [s for s in self.sensory_details if s.sense.lower() == sense_type.lower()]

    def to_description(self) -> str:
        """Convert to narrative description."""
        parts = [self.setting, self.atmosphere]

        if self.weather:
            parts.append(f"Weather: {self.weather}")
        if self.lighting:
            parts.append(f"Lighting: {self.lighting}")
        if self.architecture:
            parts.append(f"Architecture: {self.architecture}")

        return ". ".join(parts)
