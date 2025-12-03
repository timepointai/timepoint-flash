"""Character Identification schema for parallel bio generation.

Phase 1 of two-phase character generation:
1. CharacterIdentification - Fast identification of who's in the scene
2. CharacterBio generation - Parallel detailed bio generation

Examples:
    >>> from app.schemas.character_identification import CharacterStub, CharacterIdentification
    >>> stub = CharacterStub(
    ...     name="Julius Caesar",
    ...     role=CharacterRole.PRIMARY,
    ...     brief_description="Roman dictator at moment of assassination",
    ...     speaks_in_scene=True,
    ...     key_relationships=["Brutus", "Cassius"]
    ... )

Tests:
    - tests/unit/test_character_identification.py
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.characters import CharacterRole


class CharacterStub(BaseModel):
    """Lightweight character stub for identification phase.

    Used in Phase 1 to quickly identify who should be in the scene
    before generating full character bios in parallel.

    Attributes:
        name: Character name (or description for unnamed)
        role: Importance level (primary/secondary/background)
        brief_description: One-sentence description of who they are
        speaks_in_scene: Whether this character will have dialog
        key_relationships: Names of other characters they relate to

    Examples:
        >>> stub = CharacterStub(
        ...     name="Benjamin Franklin",
        ...     role=CharacterRole.PRIMARY,
        ...     brief_description="Elder statesman and founding father",
        ...     speaks_in_scene=True,
        ...     key_relationships=["John Adams", "Thomas Jefferson"]
        ... )
    """

    name: str = Field(..., description="Character name or descriptive identifier")
    role: CharacterRole = Field(
        default=CharacterRole.SECONDARY,
        description="Importance in the scene",
    )
    brief_description: str = Field(
        ...,
        description="One-sentence description of who they are in this scene",
    )
    speaks_in_scene: bool = Field(
        default=False,
        description="Whether character will have dialog",
    )
    key_relationships: list[str] = Field(
        default_factory=list,
        description="Names of other characters they interact with",
    )


class CharacterIdentification(BaseModel):
    """Result of character identification phase.

    Contains lightweight stubs for all characters to be generated,
    plus scene-level character metadata.

    Attributes:
        characters: List of CharacterStub objects (max 8)
        focal_character: Name of the primary focal character
        group_dynamics: Description of relationships between characters
        historical_accuracy_note: Note about historical accuracy

    Examples:
        >>> char_id = CharacterIdentification(
        ...     characters=[stub1, stub2, stub3],
        ...     focal_character="Thomas Jefferson",
        ...     group_dynamics="Founding fathers debating independence"
        ... )
    """

    characters: list[CharacterStub] = Field(
        ...,
        description="List of character stubs (max 8)",
    )
    focal_character: str = Field(
        ...,
        description="Name of the primary focal character",
    )
    group_dynamics: str = Field(
        ...,
        description="Description of relationships between characters",
    )
    historical_accuracy_note: str | None = Field(
        default=None,
        description="Note about historical accuracy of depictions",
    )

    @field_validator("characters")
    @classmethod
    def validate_max_characters(cls, v: list[CharacterStub]) -> list[CharacterStub]:
        """Ensure maximum 8 characters."""
        if len(v) > 8:
            # Keep most important characters
            primary = [c for c in v if c.role == CharacterRole.PRIMARY]
            secondary = [c for c in v if c.role == CharacterRole.SECONDARY]
            background = [c for c in v if c.role == CharacterRole.BACKGROUND]
            v = (primary + secondary + background)[:8]
        return v

    @property
    def primary_stubs(self) -> list[CharacterStub]:
        """Get primary character stubs."""
        return [c for c in self.characters if c.role == CharacterRole.PRIMARY]

    @property
    def speaking_stubs(self) -> list[CharacterStub]:
        """Get character stubs that will speak."""
        return [c for c in self.characters if c.speaks_in_scene]

    def get_cast_context(self) -> str:
        """Generate cast context string for bio generation.

        Returns:
            Formatted string describing all characters and their relationships.
        """
        lines = ["FULL CAST:", ""]
        for stub in self.characters:
            role_label = stub.role.value.upper()
            relations = ", ".join(stub.key_relationships) if stub.key_relationships else "none"
            speaks = " [SPEAKS]" if stub.speaks_in_scene else ""
            lines.append(f"- {stub.name} ({role_label}){speaks}")
            lines.append(f"  Description: {stub.brief_description}")
            lines.append(f"  Relates to: {relations}")
            lines.append("")

        lines.append(f"FOCAL CHARACTER: {self.focal_character}")
        lines.append(f"GROUP DYNAMICS: {self.group_dynamics}")

        return "\n".join(lines)
