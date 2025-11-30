"""Camera step schema for composition and framing.

The Camera step determines visual composition, shot type,
and cinematographic choices for the scene.

Examples:
    >>> from app.schemas.camera import CameraData
    >>> camera = CameraData(
    ...     shot_type="wide establishing",
    ...     angle="eye level",
    ...     focal_point="John Hancock at the signing table"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_camera_data_valid
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CameraData(BaseModel):
    """Compositional and framing data for the scene.

    Defines how the scene should be visually composed
    for maximum impact.

    Attributes:
        shot_type: Type of shot (wide, medium, close-up, etc.)
        angle: Camera angle (eye level, low, high, dutch, etc.)
        focal_point: Primary visual focus
        depth_of_field: Focus style (deep, shallow, etc.)
        movement: Any camera movement
        composition_rule: Compositional guideline used
        foreground_elements: Elements in foreground
        background_elements: Elements in background
    """

    # Shot definition
    shot_type: str = Field(
        default="medium wide",
        description="Shot type (establishing, wide, medium, close-up, extreme close-up)",
    )
    angle: str = Field(
        default="eye level",
        description="Camera angle (eye level, low angle, high angle, dutch, bird's eye)",
    )

    # Focus
    focal_point: str = Field(
        ...,
        description="Primary visual focus of the shot",
    )
    secondary_focus: str | None = Field(
        default=None,
        description="Secondary point of interest",
    )
    depth_of_field: str = Field(
        default="moderate",
        description="Depth of field (deep, shallow, selective)",
    )

    # Movement
    movement: str | None = Field(
        default=None,
        description="Camera movement if any (static, pan, dolly, crane)",
    )

    # Composition
    composition_rule: str = Field(
        default="rule of thirds",
        description="Compositional guideline (rule of thirds, golden ratio, symmetry, etc.)",
    )
    leading_lines: list[str] = Field(
        default_factory=list,
        description="Visual lines that draw the eye",
    )

    # Layers
    foreground_elements: list[str] = Field(
        default_factory=list,
        description="Objects/people in foreground",
    )
    midground_elements: list[str] = Field(
        default_factory=list,
        description="Objects/people in midground",
    )
    background_elements: list[str] = Field(
        default_factory=list,
        description="Objects/people in background",
    )

    # Mood
    framing_intent: str | None = Field(
        default=None,
        description="Intent of the framing (intimate, epic, claustrophobic, etc.)",
    )

    def to_description(self) -> str:
        """Convert to compositional description."""
        return (
            f"{self.shot_type} shot at {self.angle}, "
            f"focused on {self.focal_point}, "
            f"using {self.composition_rule}"
        )
