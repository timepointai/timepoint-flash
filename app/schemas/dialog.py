"""Dialog step schema for dialog generation.

The Dialog step creates up to 7 lines of dialog for the scene,
capturing the moment's conversation.

Examples:
    >>> from app.schemas.dialog import DialogData, DialogLine
    >>> line = DialogLine(
    ...     speaker="John Hancock",
    ...     text="Gentlemen, the question is now before you.",
    ...     tone="formal",
    ...     action="stands at the front of the room"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_dialog_line_valid
    - tests/unit/test_schemas.py::test_dialog_data_max_seven
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DialogLine(BaseModel):
    """A single line of dialog.

    Attributes:
        speaker: Name of the speaking character
        text: The dialog text
        tone: Emotional tone of delivery
        action: Physical action while speaking
        direction: Stage direction note
        is_whispered: Whether spoken quietly
        response_to: Name of character being addressed

    Examples:
        >>> line = DialogLine(
        ...     speaker="Benjamin Franklin",
        ...     text="We must all hang together, or most assuredly we shall all hang separately.",
        ...     tone="wry humor"
        ... )
    """

    speaker: str = Field(..., description="Name of the speaking character")
    text: str = Field(..., description="The dialog text")

    # Delivery
    tone: str | None = Field(
        default=None,
        description="Emotional tone (formal, urgent, whispered, etc.)",
    )
    is_whispered: bool = Field(
        default=False,
        description="Whether spoken quietly/whispered",
    )

    # Actions
    action: str | None = Field(
        default=None,
        description="Physical action while speaking",
    )
    direction: str | None = Field(
        default=None,
        description="Stage direction note",
    )

    # Context
    response_to: str | None = Field(
        default=None,
        description="Character being addressed or responded to",
    )

    def to_script_format(self) -> str:
        """Convert to screenplay-style format."""
        parts = [f"{self.speaker.upper()}"]
        if self.tone:
            parts.append(f"({self.tone})")
        parts.append(f'"{self.text}"')
        if self.action:
            parts.append(f"[{self.action}]")
        return " ".join(parts)


class DialogData(BaseModel):
    """Collection of dialog lines for the scene.

    Maximum of 7 lines for a single scene moment.

    Attributes:
        lines: List of dialog lines (max 7)
        scene_context: Context for the conversation
        language_style: Period-appropriate language style
        historical_accuracy_note: Note about dialog accuracy

    Examples:
        >>> data = DialogData(
        ...     lines=[
        ...         DialogLine(speaker="Adams", text="The die is cast."),
        ...         DialogLine(speaker="Franklin", text="Indeed it is."),
        ...     ],
        ...     language_style="18th century formal English"
        ... )
    """

    lines: list[DialogLine] = Field(
        ...,
        description="Dialog lines (max 7)",
    )
    scene_context: str | None = Field(
        default=None,
        description="Context for the conversation",
    )
    language_style: str | None = Field(
        default=None,
        description="Period-appropriate language style description",
    )
    historical_accuracy_note: str | None = Field(
        default=None,
        description="Note about historical accuracy of dialog",
    )

    @field_validator("lines")
    @classmethod
    def validate_max_lines(cls, v: list[DialogLine]) -> list[DialogLine]:
        """Ensure maximum 7 lines."""
        return v[:7] if len(v) > 7 else v

    @property
    def speakers(self) -> list[str]:
        """Get unique speaker names."""
        return list(dict.fromkeys(line.speaker for line in self.lines))

    @property
    def line_count(self) -> int:
        """Get number of dialog lines."""
        return len(self.lines)

    def get_lines_by_speaker(self, speaker: str) -> list[DialogLine]:
        """Get all lines by a specific speaker."""
        return [line for line in self.lines if line.speaker.lower() == speaker.lower()]

    def to_script(self) -> str:
        """Convert to full script format."""
        if self.scene_context:
            parts = [f"[{self.scene_context}]\n"]
        else:
            parts = []

        for line in self.lines:
            parts.append(line.to_script_format())

        return "\n\n".join(parts)
