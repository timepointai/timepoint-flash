"""Image prompt step schema for prompt assembly.

The Image Prompt step assembles all scene data into a comprehensive
prompt for image generation (up to 11K characters).

Examples:
    >>> from app.schemas.image_prompt import ImagePromptData
    >>> prompt = ImagePromptData(
    ...     full_prompt="A detailed historical scene...",
    ...     style="photorealistic historical painting",
    ...     aspect_ratio="16:9"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_image_prompt_valid
    - tests/unit/test_schemas.py::test_image_prompt_length
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImagePromptData(BaseModel):
    """Assembled prompt for image generation.

    Attributes:
        full_prompt: The complete image generation prompt
        style: Visual style description
        aspect_ratio: Target aspect ratio
        composition_notes: Camera/composition guidance
        character_placements: Character positioning notes
        lighting_direction: Specific lighting guidance
        color_guidance: Color palette guidance
        historical_accuracy: Period accuracy notes
        negative_prompt: Things to avoid

    Examples:
        >>> data = ImagePromptData(
        ...     full_prompt="Interior of Independence Hall, July 4, 1776...",
        ...     style="photorealistic historical",
        ...     aspect_ratio="16:9"
        ... )
    """

    # Core prompt
    full_prompt: str = Field(
        ...,
        description="Complete image generation prompt",
        max_length=15000,  # Allow up to 15K chars
    )

    # Style
    style: str = Field(
        default="photorealistic historical painting",
        description="Visual style for generation",
    )
    medium: str | None = Field(
        default=None,
        description="Art medium (oil painting, photograph, etc.)",
    )

    # Composition
    aspect_ratio: str = Field(
        default="16:9",
        description="Target aspect ratio",
    )
    composition_notes: str | None = Field(
        default=None,
        description="Camera angle and composition guidance",
    )
    camera_angle: str | None = Field(
        default=None,
        description="Specific camera angle (eye-level, low angle, etc.)",
    )
    focal_length: str | None = Field(
        default=None,
        description="Simulated focal length (wide, normal, telephoto)",
    )

    # Character placement
    character_placements: list[str] = Field(
        default_factory=list,
        description="Character positioning notes",
    )

    # Lighting and color
    lighting_direction: str | None = Field(
        default=None,
        description="Specific lighting guidance",
    )
    color_guidance: str | None = Field(
        default=None,
        description="Color palette and mood",
    )

    # Quality and accuracy
    quality_tags: list[str] = Field(
        default_factory=lambda: ["highly detailed", "8k", "masterpiece"],
        description="Quality enhancement tags",
    )
    historical_accuracy: str | None = Field(
        default=None,
        description="Historical accuracy notes for the image",
    )

    # Negative prompt
    negative_prompt: str | None = Field(
        default=None,
        description="Elements to avoid in generation",
    )

    # Anachronism prevention (auto-injected based on era)
    era_negative_prompts: list[str] = Field(
        default_factory=list,
        description="Era-specific elements to exclude (auto-generated)",
    )
    historical_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for historical accuracy (0-1)",
    )
    anachronism_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings about potential anachronisms",
    )
    distinguishing_guidance: str | None = Field(
        default=None,
        description="Guidance to distinguish from commonly confused eras",
    )

    @property
    def prompt_length(self) -> int:
        """Get the length of the full prompt."""
        return len(self.full_prompt)

    @property
    def is_within_limit(self) -> bool:
        """Check if prompt is within typical limits (11K)."""
        return self.prompt_length <= 11000

    def get_enhanced_prompt(self) -> str:
        """Get prompt with quality tags appended."""
        tags = ", ".join(self.quality_tags)
        return f"{self.full_prompt}, {tags}"

    def get_combined_negative_prompt(self) -> str | None:
        """Get all negative prompts combined into one string."""
        all_negatives = []

        # Add LLM-generated negative prompt
        if self.negative_prompt:
            all_negatives.append(self.negative_prompt)

        # Add era-specific negative prompts
        if self.era_negative_prompts:
            all_negatives.extend(self.era_negative_prompts)

        if not all_negatives:
            return None

        return ", ".join(all_negatives)

    def to_generation_params(self) -> dict:
        """Convert to image generation parameters."""
        params = {
            "prompt": self.get_enhanced_prompt(),
            "aspect_ratio": self.aspect_ratio,
        }
        combined_negative = self.get_combined_negative_prompt()
        if combined_negative:
            params["negative_prompt"] = combined_negative
        return params


class MomentData(BaseModel):
    """Combined moment data before image prompt assembly.

    Aggregates timeline, scene, characters, and dialog for
    the image prompt generation step.

    Attributes:
        query: Original query
        timeline_summary: Condensed timeline info
        scene_summary: Condensed scene info
        character_summary: Condensed character info
        dialog_summary: Key dialog context
        dramatic_focus: The dramatic focus of the moment
    """

    query: str = Field(..., description="Original user query")
    timeline_summary: str = Field(..., description="Condensed timeline information")
    scene_summary: str = Field(..., description="Condensed scene description")
    character_summary: str = Field(..., description="Condensed character information")
    dialog_summary: str | None = Field(
        default=None,
        description="Key dialog context",
    )
    dramatic_focus: str | None = Field(
        default=None,
        description="The dramatic/emotional focus of the moment",
    )
    visual_focus: str | None = Field(
        default=None,
        description="The visual focal point",
    )
