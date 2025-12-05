"""Character Interaction API endpoints.

Provides REST API for character chat, dialog extension, and surveys.

Endpoints:
    POST /api/v1/interactions/{timepoint_id}/chat - Chat with a character
    POST /api/v1/interactions/{timepoint_id}/chat/stream - Stream chat response
    POST /api/v1/interactions/{timepoint_id}/dialog - Generate more dialog
    POST /api/v1/interactions/{timepoint_id}/dialog/stream - Stream dialog
    POST /api/v1/interactions/{timepoint_id}/survey - Survey characters
    POST /api/v1/interactions/{timepoint_id}/survey/stream - Stream survey
    GET /api/v1/interactions/sessions/{timepoint_id} - List chat sessions
    GET /api/v1/interactions/sessions/{session_id} - Get chat session

Examples:
    >>> # Chat with a character
    >>> POST /api/v1/interactions/abc123/chat
    >>> {"character": "Benjamin Franklin", "message": "What do you think?"}

Tests:
    - tests/integration/test_api_interactions.py
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.character_chat import (
    CharacterChatAgent,
    ChatInput,
    ChatSessionManager,
    get_session_manager,
)
from app.agents.dialog_extension import DialogExtensionAgent, DialogExtensionInput
from app.agents.survey import SurveyAgent, SurveyInput
from app.database import get_db_session
from app.models import Timepoint
from app.schemas import Character, CharacterData, DialogData, DialogLine
from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatRole,
    ChatSession,
    ChatSessionSummary,
    DialogExtensionRequest,
    DialogExtensionResponse,
    ResponseFormat,
    SurveyMode,
    SurveyRequest,
    SurveyResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interactions", tags=["interactions"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class ChatAPIRequest(BaseModel):
    """Request to chat with a character.

    Attributes:
        character: Name of the character to chat with
        message: User's message
        session_id: Optional session ID to continue conversation
        save_session: Whether to persist session
        model: Optional model override
        response_format: Response format preference
    """

    character: str = Field(..., description="Character name to chat with")
    message: str = Field(..., min_length=1, description="User's message")
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


class ChatAPIResponse(BaseModel):
    """Response from character chat.

    Attributes:
        character_name: Name of responding character
        response: Character's response text
        session_id: Session ID for continuation
        emotional_tone: Detected emotional tone
        latency_ms: Response time in milliseconds
    """

    character_name: str
    response: str
    session_id: str | None = None
    emotional_tone: str | None = None
    latency_ms: int


class DialogAPIRequest(BaseModel):
    """Request to extend dialog.

    Attributes:
        characters: Character names or "all"
        num_lines: Number of lines to generate
        prompt: Optional direction for the dialog
        sequential: Use sequential roleplay generation
        model: Optional model override
        response_format: Response format preference
    """

    characters: list[str] | Literal["all"] = Field(
        default="all",
        description="Characters to include ('all' or list of names)",
    )
    num_lines: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of dialog lines to generate",
    )
    prompt: str | None = Field(
        default=None,
        description="Optional direction/scenario for the dialog",
    )
    sequential: bool = Field(
        default=True,
        description="Use sequential roleplay generation (more authentic)",
    )
    model: str | None = Field(
        default=None,
        description="Model override (e.g., 'gemini-2.5-flash', 'google/gemini-2.0-flash-001')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.AUTO,
        description="Response format: 'structured' (JSON), 'text' (plain), 'auto' (detect)",
    )


class DialogAPIResponse(BaseModel):
    """Response with generated dialog.

    Attributes:
        dialog: List of generated dialog lines
        context: Description of what happened
        characters_involved: Characters who spoke
        latency_ms: Generation time
    """

    dialog: list[dict[str, Any]]
    context: str | None = None
    characters_involved: list[str]
    latency_ms: int


class SurveyAPIRequest(BaseModel):
    """Request to survey characters.

    Attributes:
        characters: Character names or "all"
        questions: Questions to ask
        mode: Execution mode (parallel/sequential)
        chain_prompts: Share responses in sequential mode
        include_summary: Generate summary of responses
        model: Optional model override
        response_format: Response format preference
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
        description="In sequential mode, share prior answers",
    )
    include_summary: bool = Field(
        default=True,
        description="Generate summary of responses",
    )
    model: str | None = Field(
        default=None,
        description="Model override (e.g., 'gemini-2.5-flash', 'google/gemini-2.0-flash-001')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.AUTO,
        description="Response format: 'structured' (JSON), 'text' (plain), 'auto' (detect)",
    )


class SurveyAPIResponse(BaseModel):
    """Response with survey results.

    Attributes:
        timepoint_id: Associated timepoint
        questions: Questions asked
        responses: All character responses
        summary: Summary of responses
        mode: Execution mode used
        total_characters: Number surveyed
        latency_ms: Total time
    """

    timepoint_id: str
    questions: list[str]
    responses: list[dict[str, Any]]
    summary: str | None = None
    mode: str
    total_characters: int
    latency_ms: int


class SessionListResponse(BaseModel):
    """List of chat sessions."""

    sessions: list[ChatSessionSummary]
    total: int


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def get_timepoint_with_characters(
    timepoint_id: str,
    session: AsyncSession,
) -> tuple[Timepoint, CharacterData]:
    """Get timepoint and parse character data.

    Args:
        timepoint_id: Timepoint ID
        session: Database session

    Returns:
        Tuple of (Timepoint, CharacterData)

    Raises:
        HTTPException: If not found or no character data
    """
    result = await session.execute(
        select(Timepoint).where(Timepoint.id == timepoint_id)
    )
    timepoint = result.scalar_one_or_none()

    if not timepoint:
        raise HTTPException(status_code=404, detail="Timepoint not found")

    if not timepoint.character_data_json:
        raise HTTPException(
            status_code=404,
            detail="Timepoint has no character data. Generation may be incomplete.",
        )

    try:
        char_data = CharacterData.model_validate(timepoint.character_data_json)
    except Exception as e:
        logger.error(f"Failed to parse character data: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse character data")

    return timepoint, char_data


def get_character_by_name(
    char_data: CharacterData,
    name: str,
) -> Character:
    """Find character by name (case-insensitive).

    Args:
        char_data: CharacterData with characters
        name: Character name to find

    Returns:
        Character object

    Raises:
        HTTPException: If character not found
    """
    char = char_data.get_character_by_name(name)
    if not char:
        available = [c.name for c in char_data.characters]
        raise HTTPException(
            status_code=404,
            detail=f"Character '{name}' not found. Available: {available}",
        )
    return char


def filter_characters(
    char_data: CharacterData,
    names: list[str] | Literal["all"],
) -> list[Character]:
    """Filter characters by names.

    Args:
        char_data: CharacterData with characters
        names: List of names or "all"

    Returns:
        List of Character objects
    """
    if names == "all":
        return char_data.characters

    result = []
    for name in names:
        char = char_data.get_character_by_name(name)
        if char:
            result.append(char)

    if not result:
        available = [c.name for c in char_data.characters]
        raise HTTPException(
            status_code=404,
            detail=f"No matching characters found. Available: {available}",
        )

    return result


def get_existing_dialog(timepoint: Timepoint) -> list[DialogLine]:
    """Parse existing dialog from timepoint.

    Args:
        timepoint: Timepoint with dialog_json

    Returns:
        List of DialogLine objects (empty if none)
    """
    if not timepoint.dialog_json:
        return []

    try:
        return [DialogLine.model_validate(line) for line in timepoint.dialog_json]
    except Exception:
        return []


# =============================================================================
# CHAT ENDPOINTS
# =============================================================================


@router.post("/{timepoint_id}/chat", response_model=ChatAPIResponse)
async def chat_with_character(
    timepoint_id: str,
    request: ChatAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ChatAPIResponse:
    """Chat with a character from the timepoint.

    Sends a message to a character and receives an in-character response.
    Optionally continues an existing conversation session.

    Args:
        timepoint_id: Timepoint UUID
        request: Chat request with character and message
        db: Database session

    Returns:
        ChatAPIResponse with character's response

    Example:
        ```json
        POST /api/v1/interactions/abc123/chat
        {
            "character": "Benjamin Franklin",
            "message": "What do you think of this document?"
        }
        ```
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)
    character = get_character_by_name(char_data, request.character)

    # Get session manager and history
    session_manager = get_session_manager()
    history: list[ChatMessage] = []
    session_id = request.session_id

    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            history = session.messages

    # Build input
    chat_input = ChatInput.from_timepoint_data(
        character=character,
        message=request.message,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        scene_context=timepoint.scene_data_json.get("setting", "") if timepoint.scene_data_json else "",
        history=history,
    )

    # Run chat agent with model and response_format
    agent = CharacterChatAgent(
        model=request.model,
        response_format=request.response_format,
    )
    result = await agent.chat(chat_input)

    if not result.success or not result.content:
        raise HTTPException(
            status_code=500,
            detail=result.error or "Chat generation failed",
        )

    # Update session if requested
    if request.save_session or session_id:
        if not session_id:
            session = session_manager.create_session(timepoint_id, character.name)
            session_id = session.id

        session_manager.add_message(session_id, "user", request.message)
        session_manager.add_message(
            session_id,
            "character",
            result.content.response,
            character.name,
        )

    return ChatAPIResponse(
        character_name=result.content.character_name,
        response=result.content.response,
        session_id=session_id,
        emotional_tone=result.content.emotional_tone,
        latency_ms=result.latency_ms,
    )


@router.post("/{timepoint_id}/chat/stream")
async def chat_with_character_stream(
    timepoint_id: str,
    request: ChatAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream chat response from a character.

    Returns Server-Sent Events with tokens as they're generated.

    Args:
        timepoint_id: Timepoint UUID
        request: Chat request
        db: Database session

    Returns:
        StreamingResponse with SSE events
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)
    character = get_character_by_name(char_data, request.character)

    # Get history if session exists
    session_manager = get_session_manager()
    history: list[ChatMessage] = []

    if request.session_id:
        session = session_manager.get_session(request.session_id)
        if session:
            history = session.messages

    # Build input
    chat_input = ChatInput.from_timepoint_data(
        character=character,
        message=request.message,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        scene_context=timepoint.scene_data_json.get("setting", "") if timepoint.scene_data_json else "",
        history=history,
    )

    async def stream_response() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        agent = CharacterChatAgent(
            model=request.model,
            response_format=request.response_format,
        )
        full_response = ""

        try:
            async for token in agent.chat_stream(chat_input):
                full_response += token
                event = {
                    "event": "token",
                    "data": token,
                    "character_name": character.name,
                }
                yield f"data: {json.dumps(event)}\n\n"

            # Done event
            event = {
                "event": "done",
                "data": full_response,
                "character_name": character.name,
            }
            yield f"data: {json.dumps(event)}\n\n"

            # Update session if requested
            if request.save_session or request.session_id:
                session_id = request.session_id
                if not session_id:
                    session = session_manager.create_session(timepoint_id, character.name)
                    session_id = session.id

                session_manager.add_message(session_id, "user", request.message)
                session_manager.add_message(session_id, "character", full_response, character.name)

        except Exception as e:
            event = {"event": "error", "data": str(e)}
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# DIALOG EXTENSION ENDPOINTS
# =============================================================================


@router.post("/{timepoint_id}/dialog", response_model=DialogAPIResponse)
async def extend_dialog(
    timepoint_id: str,
    request: DialogAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> DialogAPIResponse:
    """Generate additional dialog for the timepoint.

    Extends the existing dialog with new lines, optionally with
    a specific direction/scenario.

    Args:
        timepoint_id: Timepoint UUID
        request: Dialog extension request
        db: Database session

    Returns:
        DialogAPIResponse with new dialog lines

    Example:
        ```json
        POST /api/v1/interactions/abc123/dialog
        {
            "characters": ["Benjamin Franklin", "John Adams"],
            "num_lines": 5,
            "prompt": "They begin discussing the wording of the document"
        }
        ```
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)

    # Filter characters
    selected_chars = filter_characters(char_data, request.characters)
    char_names = [c.name for c in selected_chars] if request.characters != "all" else None

    # Get existing dialog
    existing_dialog = get_existing_dialog(timepoint)

    # Build input
    dialog_input = DialogExtensionInput.from_timepoint_data(
        characters=char_data,
        existing_dialog=existing_dialog,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        setting=timepoint.scene_data_json.get("setting", "") if timepoint.scene_data_json else "",
        atmosphere=timepoint.scene_data_json.get("atmosphere", "") if timepoint.scene_data_json else "",
        num_lines=request.num_lines,
        prompt=request.prompt,
        selected_characters=char_names,
    )

    # Run agent with model and response_format
    agent = DialogExtensionAgent(
        model=request.model,
        response_format=request.response_format,
    )

    if request.sequential:
        result = await agent.extend_sequential(dialog_input)
    else:
        result = await agent.extend(dialog_input)

    if not result.success or not result.content:
        raise HTTPException(
            status_code=500,
            detail=result.error or "Dialog generation failed",
        )

    return DialogAPIResponse(
        dialog=result.content.dialog,
        context=result.content.context,
        characters_involved=result.content.characters_involved,
        latency_ms=result.latency_ms,
    )


@router.post("/{timepoint_id}/dialog/stream")
async def extend_dialog_stream(
    timepoint_id: str,
    request: DialogAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream dialog generation line by line.

    Returns SSE events as each dialog line is generated.

    Args:
        timepoint_id: Timepoint UUID
        request: Dialog extension request
        db: Database session

    Returns:
        StreamingResponse with SSE events
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)

    # Filter characters
    char_names = None
    if request.characters != "all":
        selected_chars = filter_characters(char_data, request.characters)
        char_names = [c.name for c in selected_chars]

    # Get existing dialog
    existing_dialog = get_existing_dialog(timepoint)

    # Build input
    dialog_input = DialogExtensionInput.from_timepoint_data(
        characters=char_data,
        existing_dialog=existing_dialog,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        setting=timepoint.scene_data_json.get("setting", "") if timepoint.scene_data_json else "",
        atmosphere=timepoint.scene_data_json.get("atmosphere", "") if timepoint.scene_data_json else "",
        num_lines=request.num_lines,
        prompt=request.prompt,
        selected_characters=char_names,
    )

    async def stream_dialog() -> AsyncGenerator[str, None]:
        """Generate SSE events for dialog."""
        agent = DialogExtensionAgent(
            model=request.model,
            response_format=request.response_format,
        )

        try:
            async for line_data in agent.extend_stream(dialog_input):
                event = {"event": "line" if "speaker" in line_data else "done", "data": line_data}
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            event = {"event": "error", "data": str(e)}
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream_dialog(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# SURVEY ENDPOINTS
# =============================================================================


@router.post("/{timepoint_id}/survey", response_model=SurveyAPIResponse)
async def survey_characters(
    timepoint_id: str,
    request: SurveyAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SurveyAPIResponse:
    """Survey characters with questions.

    Ask the same question(s) to multiple characters and get
    structured responses with sentiment analysis.

    Args:
        timepoint_id: Timepoint UUID
        request: Survey request
        db: Database session

    Returns:
        SurveyAPIResponse with all responses

    Example:
        ```json
        POST /api/v1/interactions/abc123/survey
        {
            "characters": "all",
            "questions": ["How do you feel about this moment?"],
            "mode": "parallel"
        }
        ```
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)

    # Filter characters
    selected_chars = filter_characters(char_data, request.characters)
    char_names = [c.name for c in selected_chars] if request.characters != "all" else None

    # Build input
    survey_input = SurveyInput.from_timepoint_data(
        characters=char_data,
        questions=request.questions,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        mode=request.mode,
        chain_prompts=request.chain_prompts,
        include_summary=request.include_summary,
        selected_characters=char_names,
    )

    # Run agent with model and response_format
    agent = SurveyAgent(
        model=request.model,
        response_format=request.response_format,
    )
    result = await agent.survey(survey_input)

    if not result.success or not result.content:
        raise HTTPException(
            status_code=500,
            detail=result.error or "Survey failed",
        )

    # Convert responses to dicts
    responses = [
        {
            "character_name": r.character_name,
            "question": r.question,
            "response": r.response,
            "sentiment": r.sentiment,
            "key_points": r.key_points,
            "emotional_tone": r.emotional_tone,
        }
        for r in result.content.responses
    ]

    return SurveyAPIResponse(
        timepoint_id=timepoint_id,
        questions=result.content.questions,
        responses=responses,
        summary=result.content.summary,
        mode=result.content.mode.value,
        total_characters=result.content.total_characters,
        latency_ms=result.latency_ms,
    )


@router.post("/{timepoint_id}/survey/stream")
async def survey_characters_stream(
    timepoint_id: str,
    request: SurveyAPIRequest,
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream survey results as each character responds.

    Returns SSE events with progress updates.

    Args:
        timepoint_id: Timepoint UUID
        request: Survey request
        db: Database session

    Returns:
        StreamingResponse with SSE events
    """
    # Get timepoint and characters
    timepoint, char_data = await get_timepoint_with_characters(timepoint_id, db)

    # Filter characters
    char_names = None
    if request.characters != "all":
        selected_chars = filter_characters(char_data, request.characters)
        char_names = [c.name for c in selected_chars]

    # Build input
    survey_input = SurveyInput.from_timepoint_data(
        characters=char_data,
        questions=request.questions,
        year=timepoint.year or 0,
        location=timepoint.location or "Unknown",
        era=timepoint.era,
        mode=request.mode,
        chain_prompts=request.chain_prompts,
        include_summary=request.include_summary,
        selected_characters=char_names,
    )

    async def stream_survey() -> AsyncGenerator[str, None]:
        """Generate SSE events for survey."""
        agent = SurveyAgent(
            model=request.model,
            response_format=request.response_format,
        )

        try:
            async for event_data in agent.survey_stream(survey_input):
                yield f"data: {json.dumps(event_data)}\n\n"

        except Exception as e:
            event = {"event": "error", "data": str(e)}
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream_survey(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =============================================================================
# SESSION ENDPOINTS
# =============================================================================


@router.get("/sessions/{timepoint_id}", response_model=SessionListResponse)
async def list_chat_sessions(
    timepoint_id: str,
) -> SessionListResponse:
    """List chat sessions for a timepoint.

    Args:
        timepoint_id: Timepoint UUID

    Returns:
        SessionListResponse with session summaries
    """
    session_manager = get_session_manager()
    sessions = session_manager.get_sessions_for_timepoint(timepoint_id)

    summaries = [
        ChatSessionSummary(
            id=s.id,
            character_name=s.character_name,
            message_count=len(s.messages),
            last_message_preview=s.messages[-1].content[:50] if s.messages else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]

    return SessionListResponse(
        sessions=summaries,
        total=len(summaries),
    )


@router.get("/session/{session_id}", response_model=ChatSession)
async def get_chat_session(
    session_id: str,
) -> ChatSession:
    """Get a chat session by ID.

    Args:
        session_id: Session UUID

    Returns:
        ChatSession with full message history

    Raises:
        HTTPException: If session not found
    """
    session_manager = get_session_manager()
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/session/{session_id}")
async def delete_chat_session(
    session_id: str,
) -> dict[str, Any]:
    """Delete a chat session.

    Args:
        session_id: Session UUID

    Returns:
        Confirmation message

    Raises:
        HTTPException: If session not found
    """
    session_manager = get_session_manager()

    if not session_manager.delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True, "session_id": session_id}
