"""Characters step schema for character generation.

The Characters step creates up to 8 characters for the scene,
including historical figures and background characters.

Examples:
    >>> from app.schemas.characters import CharacterData, Character, CharacterRole
    >>> john_hancock = Character(
    ...     name="John Hancock",
    ...     role=CharacterRole.PRIMARY,
    ...     description="President of Congress, tall with commanding presence",
    ...     clothing="Fine colonial attire with powdered wig"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_character_valid
    - tests/unit/test_schemas.py::test_character_data_max_eight
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class CharacterRole(str, Enum):
    """Role importance in the scene."""

    PRIMARY = "primary"  # Main focus characters (1-2)
    SECONDARY = "secondary"  # Important supporting (2-3)
    BACKGROUND = "background"  # Background/atmosphere (3-5)


class Character(BaseModel):
    """A single character in the scene.

    Attributes:
        name: Character name (or description for unnamed)
        role: Importance level in scene
        description: Physical description
        clothing: Clothing and accessories
        expression: Facial expression
        pose: Body posture and pose
        action: Current action or activity
        historical_note: Historical context if known figure
        age_description: Approximate age description
        position_in_scene: Where they are in the scene

    Examples:
        >>> char = Character(
        ...     name="Benjamin Franklin",
        ...     role=CharacterRole.PRIMARY,
        ...     description="Elderly statesman with spectacles",
        ...     expression="Thoughtful, slightly amused"
        ... )
    """

    name: str = Field(..., description="Character name or descriptive identifier")
    role: CharacterRole = Field(
        default=CharacterRole.SECONDARY,
        description="Importance in the scene",
    )

    # Physical appearance
    description: str = Field(
        ...,
        description="Physical description",
    )
    clothing: str | None = Field(
        default=None,
        description="Clothing and accessories",
    )
    expression: str | None = Field(
        default=None,
        description="Facial expression",
    )
    pose: str | None = Field(
        default=None,
        description="Body posture and pose",
    )

    # Actions and context
    action: str | None = Field(
        default=None,
        description="Current action or activity",
    )
    position_in_scene: str | None = Field(
        default=None,
        description="Location within the scene",
    )

    # Character details
    age_description: str | None = Field(
        default=None,
        description="Approximate age (e.g., 'middle-aged', 'elderly')",
    )
    historical_note: str | None = Field(
        default=None,
        description="Historical context for known figures",
    )

    # Dialog and personality (for roleplay-informed dialog generation)
    personality: str | None = Field(
        default=None,
        description="Core personality traits (e.g., 'witty, diplomatic, cautious')",
    )
    speaking_style: str | None = Field(
        default=None,
        description="How they speak (e.g., 'formal, verbose, uses metaphors')",
    )
    voice_notes: str | None = Field(
        default=None,
        description="Speech patterns, accent hints, verbal quirks",
    )
    emotional_state: str | None = Field(
        default=None,
        description="Current emotional state in this scene",
    )

    # Dialog participation
    speaks_in_scene: bool = Field(
        default=False,
        description="Whether character has dialog",
    )

    def to_prompt_description(self) -> str:
        """Convert to description for image prompt."""
        parts = [self.name]
        if self.description:
            parts.append(self.description)
        if self.clothing:
            parts.append(f"wearing {self.clothing}")
        if self.expression:
            parts.append(f"expression: {self.expression}")
        if self.pose:
            parts.append(f"pose: {self.pose}")
        if self.action:
            parts.append(f"action: {self.action}")
        return ", ".join(parts)

    def to_dialog_context(self) -> str:
        """Convert to context string for dialog generation.

        Provides personality and speaking style information for
        roleplay-informed dialog generation.

        Returns:
            Formatted context string with character's voice profile.
        """
        lines = [f"**{self.name}** ({self.role.value})"]

        if self.historical_note:
            lines.append(f"  Historical: {self.historical_note}")
        if self.personality:
            lines.append(f"  Personality: {self.personality}")
        if self.speaking_style:
            lines.append(f"  Speaking Style: {self.speaking_style}")
        if self.voice_notes:
            lines.append(f"  Voice Notes: {self.voice_notes}")
        if self.emotional_state:
            lines.append(f"  Current State: {self.emotional_state}")
        if self.action:
            lines.append(f"  Action: {self.action}")

        return "\n".join(lines)

    def to_system_prompt(self, year: int, location: str, era: str | None = None) -> str:
        """Convert to roleplay system prompt for sequential dialog generation.

        Creates a system prompt that makes the LLM "become" this character,
        enabling authentic, personality-driven dialog generation.

        Args:
            year: The year of the scene
            location: The location of the scene
            era: Historical era (e.g., "Colonial America")

        Returns:
            System prompt string for roleplay-based dialog generation.

        Examples:
            >>> char = Character(name="Ben Franklin", personality="witty", ...)
            >>> prompt = char.to_system_prompt(1776, "Philadelphia")
            >>> # "You are Ben Franklin..."
        """
        era_str = f" ({era})" if era else ""
        year_display = f"{abs(year)} BCE" if year < 0 else str(year)

        lines = [f"You are {self.name}."]

        # Add historical context if known figure
        if self.historical_note:
            lines.append(f"\nHISTORICAL CONTEXT: {self.historical_note}")

        # Add personality and speaking characteristics
        if self.personality:
            lines.append(f"\nPERSONALITY: {self.personality}")
        if self.speaking_style:
            lines.append(f"SPEAKING STYLE: {self.speaking_style}")
        if self.voice_notes:
            lines.append(f"VOICE: {self.voice_notes}")
        if self.emotional_state:
            lines.append(f"CURRENT EMOTIONAL STATE: {self.emotional_state}")
        if self.action:
            lines.append(f"CURRENT ACTION: {self.action}")

        # Add scene context
        lines.append(f"\nSCENE: You are in {location}, {year_display}{era_str}.")

        # Add roleplay instructions
        lines.append("""
INSTRUCTIONS:
- Stay completely in character as this person
- Match your personality traits in HOW you speak
- Use your speaking style for word choice and sentence structure
- Your sentence length, vocabulary, and directness MUST reflect your social class
- Reflect your emotional state in your delivery
- Respond naturally to what others say
- Give only your spoken dialog (1-2 sentences)
- Do NOT include stage directions or your name
- Do NOT break character or add meta-commentary
- Do NOT use modern English idioms or anachronistic references
- Use culturally correct deity names and expressions for this time/place""")

        return "\n".join(lines)


class CharacterData(BaseModel):
    """Collection of all characters in the scene.

    Maximum of 8 characters per scene for visual clarity.

    Attributes:
        characters: List of characters (max 8)
        focal_character: Name of the primary focal character
        group_dynamics: Description of character relationships
        historical_accuracy_note: Note about historical accuracy

    Examples:
        >>> data = CharacterData(
        ...     characters=[
        ...         Character(name="John Adams", role=CharacterRole.PRIMARY, ...),
        ...         Character(name="Thomas Jefferson", role=CharacterRole.PRIMARY, ...),
        ...     ],
        ...     focal_character="Thomas Jefferson"
        ... )
    """

    characters: list[Character] = Field(
        ...,
        description="List of characters in the scene (max 8)",
    )
    focal_character: str | None = Field(
        default=None,
        description="Name of the primary focal character",
    )
    group_dynamics: str | None = Field(
        default=None,
        description="Description of relationships between characters",
    )
    historical_accuracy_note: str | None = Field(
        default=None,
        description="Note about historical accuracy of depictions",
    )

    @field_validator("characters")
    @classmethod
    def validate_max_characters(cls, v: list[Character]) -> list[Character]:
        """Ensure maximum 8 characters."""
        if len(v) > 8:
            # Keep most important characters
            primary = [c for c in v if c.role == CharacterRole.PRIMARY]
            secondary = [c for c in v if c.role == CharacterRole.SECONDARY]
            background = [c for c in v if c.role == CharacterRole.BACKGROUND]
            v = (primary + secondary + background)[:8]
        return v

    @property
    def primary_characters(self) -> list[Character]:
        """Get primary characters."""
        return [c for c in self.characters if c.role == CharacterRole.PRIMARY]

    @property
    def secondary_characters(self) -> list[Character]:
        """Get secondary characters."""
        return [c for c in self.characters if c.role == CharacterRole.SECONDARY]

    @property
    def background_characters(self) -> list[Character]:
        """Get background characters."""
        return [c for c in self.characters if c.role == CharacterRole.BACKGROUND]

    @property
    def speaking_characters(self) -> list[Character]:
        """Get characters with dialog."""
        return [c for c in self.characters if c.speaks_in_scene]

    def get_character_by_name(self, name: str) -> Character | None:
        """Find character by name (case-insensitive)."""
        for char in self.characters:
            if char.name.lower() == name.lower():
                return char
        return None
