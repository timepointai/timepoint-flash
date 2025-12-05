"""Chat and interaction schemas for character conversations.

This module defines schemas for:
- Character chat (single character conversation)
- Dialog extension (generate more dialog between characters)
- Survey mode (ask questions to multiple characters)

Examples:
    >>> from app.schemas.chat import ChatRequest, SurveyRequest
    >>> chat = ChatRequest(character="Benjamin Franklin", message="What do you think?")
    >>> survey = SurveyRequest(characters=["all"], questions=["How do you feel?"])

Tests:
    - tests/unit/test_schemas_chat.py
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# CHAT SCHEMAS
# =============================================================================


class ChatRole(str, Enum):
    """Role in a chat conversation."""

    USER = "user"
    CHARACTER = "character"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single message in a chat conversation.

    Attributes:
        role: Who sent the message (user, character, system)
        content: The message text
        character_name: Name of character (if role=character)
        timestamp: When the message was sent
    """

    role: ChatRole = Field(..., description="Message sender role")
    content: str = Field(..., description="Message content")
    character_name: str | None = Field(
        default=None,
        description="Character name (if role=character)",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Message timestamp",
    )

    def to_prompt_format(self) -> str:
        """Convert to format for LLM prompt."""
        if self.role == ChatRole.USER:
            return f"User: {self.content}"
        elif self.role == ChatRole.CHARACTER:
            return f"{self.character_name or 'Character'}: {self.content}"
        else:
            return f"[System: {self.content}]"


class ResponseFormat(str, Enum):
    """Response format preference."""

    STRUCTURED = "structured"  # Use JSON schema when supported
    TEXT = "text"  # Plain text response (always works)
    AUTO = "auto"  # Auto-detect based on model capabilities


class ChatRequest(BaseModel):
    """Request to chat with a character.

    Attributes:
        character: Name of the character to chat with
        message: User's message
        session_id: Optional session ID to continue conversation
        save_session: Whether to persist session to database
        model: Optional model override for this request
        response_format: Response format preference (structured/text/auto)
    """

    character: str = Field(..., description="Character name to chat with")
    message: str = Field(..., description="User's message")
    session_id: str | None = Field(
        default=None,
        description="Session ID to continue existing conversation",
    )
    save_session: bool = Field(
        default=False,
        description="Whether to save session to database",
    )
    model: str | None = Field(
        default=None,
        description="Model override (e.g., 'gemini-2.5-flash', 'google/gemini-2.0-flash-001')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.AUTO,
        description="Response format: 'structured' (JSON), 'text' (plain), 'auto' (detect)",
    )


class ChatResponse(BaseModel):
    """Response from character chat.

    Attributes:
        character_name: Name of responding character
        response: Character's response text
        session_id: Session ID (if saved)
        in_character: Whether response is in-character
        confidence: Confidence in historical accuracy (0-1)
        emotional_tone: Detected emotional tone
    """

    character_name: str = Field(..., description="Character who responded")
    response: str = Field(..., description="Character's response")
    session_id: str | None = Field(
        default=None,
        description="Session ID for continuation",
    )
    in_character: bool = Field(
        default=True,
        description="Whether response is in-character",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Confidence in historical accuracy",
    )
    emotional_tone: str | None = Field(
        default=None,
        description="Emotional tone of response",
    )


class ChatSession(BaseModel):
    """A chat session with conversation history.

    Attributes:
        id: Unique session identifier
        timepoint_id: Associated timepoint
        character_name: Character being chatted with
        messages: Conversation history
        created_at: Session creation time
        updated_at: Last message time
    """

    id: str = Field(..., description="Unique session ID")
    timepoint_id: str = Field(..., description="Associated timepoint ID")
    character_name: str = Field(..., description="Character name")
    messages: list[ChatMessage] = Field(
        default_factory=list,
        description="Conversation history",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Session creation time",
    )
    updated_at: datetime | None = Field(
        default=None,
        description="Last update time",
    )


class ChatSessionSummary(BaseModel):
    """Summary of a chat session for listing."""

    id: str
    character_name: str
    message_count: int
    last_message_preview: str | None
    created_at: datetime
    updated_at: datetime | None


# =============================================================================
# DIALOG EXTENSION SCHEMAS
# =============================================================================


class DialogExtensionRequest(BaseModel):
    """Request to generate more dialog.

    Attributes:
        characters: Character names or "all" for all characters
        prompt: Optional scenario/direction for the dialog
        num_lines: Number of dialog lines to generate (1-10)
        continue_existing: Whether to continue from existing dialog
        model: Optional model override for this request
        response_format: Response format preference (structured/text/auto)
    """

    characters: list[str] | Literal["all"] = Field(
        default="all",
        description="Characters to include ('all' or list of names)",
    )
    prompt: str | None = Field(
        default=None,
        description="Scenario or direction for the dialog",
    )
    num_lines: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of dialog lines to generate",
    )
    continue_existing: bool = Field(
        default=True,
        description="Whether to continue from existing dialog",
    )
    model: str | None = Field(
        default=None,
        description="Model override (e.g., 'gemini-2.5-flash', 'google/gemini-2.0-flash-001')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.AUTO,
        description="Response format: 'structured' (JSON), 'text' (plain), 'auto' (detect)",
    )


class DialogExtensionResponse(BaseModel):
    """Response with generated dialog.

    Attributes:
        dialog: List of generated dialog lines
        context: Context/description of what happened
        characters_involved: Names of characters who spoke
    """

    dialog: list[dict] = Field(..., description="Generated dialog lines")
    context: str | None = Field(
        default=None,
        description="Context description",
    )
    characters_involved: list[str] = Field(
        default_factory=list,
        description="Characters who participated",
    )


# =============================================================================
# SURVEY SCHEMAS
# =============================================================================


class SurveyMode(str, Enum):
    """Survey execution mode."""

    PARALLEL = "parallel"  # Ask all at once (faster)
    SEQUENTIAL = "sequential"  # Ask one at a time (context-aware)


class SurveyRequest(BaseModel):
    """Request to survey multiple characters.

    Attributes:
        characters: Character names or "all"
        questions: List of questions to ask
        mode: Execution mode (parallel or sequential)
        chain_prompts: If sequential, whether to share prior answers
        include_summary: Whether to generate a summary
        model: Optional model override for this request
        response_format: Response format preference (structured/text/auto)
    """

    characters: list[str] | Literal["all"] = Field(
        default="all",
        description="Characters to survey ('all' or list of names)",
    )
    questions: list[str] = Field(
        ...,
        min_length=1,
        description="Questions to ask each character",
    )
    mode: SurveyMode = Field(
        default=SurveyMode.PARALLEL,
        description="Execution mode",
    )
    chain_prompts: bool = Field(
        default=False,
        description="In sequential mode, share prior answers with next character",
    )
    include_summary: bool = Field(
        default=True,
        description="Whether to generate a summary of responses",
    )
    model: str | None = Field(
        default=None,
        description="Model override (e.g., 'gemini-2.5-flash', 'google/gemini-2.0-flash-001')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.AUTO,
        description="Response format: 'structured' (JSON), 'text' (plain), 'auto' (detect)",
    )


class CharacterSurveyResponse(BaseModel):
    """A single character's survey response.

    Attributes:
        character_name: Name of the character
        question: The question asked
        response: Character's response
        sentiment: Detected sentiment (positive/negative/neutral/mixed)
        key_points: Key points extracted from response
        emotional_tone: Emotional tone of response
    """

    character_name: str = Field(..., description="Character name")
    question: str = Field(..., description="Question asked")
    response: str = Field(..., description="Character's response")
    sentiment: str | None = Field(
        default=None,
        description="Sentiment analysis (positive/negative/neutral/mixed)",
    )
    key_points: list[str] = Field(
        default_factory=list,
        description="Key points from response",
    )
    emotional_tone: str | None = Field(
        default=None,
        description="Emotional tone",
    )


class SurveyResult(BaseModel):
    """Complete survey results.

    Attributes:
        timepoint_id: Associated timepoint
        questions: Questions that were asked
        responses: All character responses
        summary: Optional summary of all responses
        mode: Mode used (parallel/sequential)
        total_characters: Number of characters surveyed
    """

    timepoint_id: str = Field(..., description="Timepoint ID")
    questions: list[str] = Field(..., description="Questions asked")
    responses: list[CharacterSurveyResponse] = Field(
        ...,
        description="All responses",
    )
    summary: str | None = Field(
        default=None,
        description="Summary of all responses",
    )
    mode: SurveyMode = Field(..., description="Execution mode used")
    total_characters: int = Field(..., description="Number of characters surveyed")

    def get_responses_by_character(self, name: str) -> list[CharacterSurveyResponse]:
        """Get all responses from a specific character."""
        return [r for r in self.responses if r.character_name.lower() == name.lower()]

    def get_responses_by_question(self, question: str) -> list[CharacterSurveyResponse]:
        """Get all responses to a specific question."""
        return [r for r in self.responses if r.question == question]


# =============================================================================
# STREAMING EVENT SCHEMAS
# =============================================================================


class ChatStreamEvent(BaseModel):
    """SSE event for chat streaming.

    Attributes:
        event: Event type (token, done, error)
        data: Event data (token text, completion, error message)
        character_name: Character name (for context)
    """

    event: Literal["token", "done", "error"] = Field(..., description="Event type")
    data: str = Field(..., description="Event data")
    character_name: str | None = Field(default=None, description="Character name")


class DialogStreamEvent(BaseModel):
    """SSE event for dialog streaming.

    Attributes:
        event: Event type (line, done, error)
        data: Event data
        speaker: Speaker name (for line events)
        line_number: Line number in sequence
    """

    event: Literal["line", "done", "error"] = Field(..., description="Event type")
    data: dict | str = Field(..., description="Event data")
    speaker: str | None = Field(default=None, description="Speaker name")
    line_number: int | None = Field(default=None, description="Line number")


class SurveyStreamEvent(BaseModel):
    """SSE event for survey streaming.

    Attributes:
        event: Event type (response, summary, done, error)
        data: Event data
        character_name: Character name (for response events)
        question: Question being answered
        progress: Progress through survey (0-100)
    """

    event: Literal["response", "summary", "done", "error"] = Field(
        ...,
        description="Event type",
    )
    data: dict | str = Field(..., description="Event data")
    character_name: str | None = Field(default=None, description="Character name")
    question: str | None = Field(default=None, description="Current question")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
