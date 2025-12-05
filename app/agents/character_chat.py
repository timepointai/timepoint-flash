"""Character Chat Agent for interactive character conversations.

Enables users to chat with characters from timepoint scenes,
maintaining conversation history and character roleplay.

Examples:
    >>> from app.agents.character_chat import CharacterChatAgent, ChatInput
    >>> agent = CharacterChatAgent()
    >>> result = await agent.chat(chat_input)
    >>> print(result.content.response)

Tests:
    - tests/unit/test_agents/test_character_chat.py
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from app.agents.base import AgentResult
from app.core.llm_router import LLMRouter
from app.core.model_capabilities import (
    get_text_model_config,
    infer_provider_from_model_id,
    supports_structured_output,
)
from app.prompts import character_chat as chat_prompts
from app.schemas import Character, CharacterData
from app.schemas.chat import (
    ChatMessage,
    ChatResponse,
    ChatRole,
    ChatSession,
    ResponseFormat,
)

logger = logging.getLogger(__name__)


# =============================================================================
# INPUT/OUTPUT SCHEMAS
# =============================================================================


@dataclass
class ChatInput:
    """Input for character chat.

    Attributes:
        character: The Character object to chat with
        message: User's message
        year: Scene year (for context)
        location: Scene location
        era: Historical era
        scene_context: Additional scene context
        history: Previous messages in this conversation
    """

    character: Character
    message: str
    year: int
    location: str
    era: str | None = None
    scene_context: str = ""
    history: list[ChatMessage] = field(default_factory=list)

    @classmethod
    def from_timepoint_data(
        cls,
        character: Character,
        message: str,
        year: int,
        location: str,
        era: str | None = None,
        scene_context: str = "",
        history: list[ChatMessage] | None = None,
    ) -> "ChatInput":
        """Create ChatInput from timepoint data.

        Args:
            character: Character to chat with
            message: User's message
            year: Scene year
            location: Scene location
            era: Historical era
            scene_context: Scene description
            history: Conversation history

        Returns:
            ChatInput instance
        """
        return cls(
            character=character,
            message=message,
            year=year,
            location=location,
            era=era,
            scene_context=scene_context,
            history=history or [],
        )


class ChatOutput(BaseModel):
    """Output from character chat.

    Attributes:
        character_name: Name of responding character
        response: Character's response text
        in_character: Whether response is in-character
        emotional_tone: Detected emotional tone
    """

    character_name: str = Field(..., description="Character who responded")
    response: str = Field(..., description="Character's response")
    in_character: bool = Field(default=True, description="Is in-character")
    emotional_tone: str | None = Field(default=None, description="Emotional tone")


# =============================================================================
# CHARACTER CHAT AGENT
# =============================================================================


class CharacterChatAgent:
    """Agent for chatting with characters from timepoint scenes.

    Maintains character roleplay using the character's bio as system prompt.
    Supports both single-turn and multi-turn conversations.

    Attributes:
        router: LLM router for API calls
        name: Agent name for logging
        model: Optional model override
        response_format: Response format preference

    Examples:
        >>> agent = CharacterChatAgent()
        >>> input_data = ChatInput(
        ...     character=benjamin_franklin,
        ...     message="What do you think of the situation?",
        ...     year=1776,
        ...     location="Philadelphia"
        ... )
        >>> result = await agent.chat(input_data)
        >>> print(result.content.response)

    Tests:
        - tests/unit/test_agents/test_character_chat.py::test_chat_basic
        - tests/unit/test_agents/test_character_chat.py::test_chat_with_history
    """

    def __init__(
        self,
        router: LLMRouter | None = None,
        name: str = "CharacterChatAgent",
        model: str | None = None,
        response_format: ResponseFormat = ResponseFormat.AUTO,
    ) -> None:
        """Initialize Character Chat Agent.

        Args:
            router: LLM router for API calls
            name: Agent name for logging
            model: Optional model override (e.g., 'gemini-2.5-flash')
            response_format: Response format preference (structured/text/auto)
        """
        self.model = model
        self.response_format = response_format

        # Create router with custom model if specified
        if model:
            provider = infer_provider_from_model_id(model)
            if provider == "google":
                self.router = router or LLMRouter(text_model=model)
            else:
                self.router = router or LLMRouter(text_model=model)
        else:
            self.router = router or LLMRouter()

        self.name = name

    def _should_use_structured(self) -> bool:
        """Determine if structured output should be used.

        Based on response_format preference and model capabilities.

        Returns:
            True if structured output should be used.
        """
        if self.response_format == ResponseFormat.TEXT:
            return False
        if self.response_format == ResponseFormat.STRUCTURED:
            return True
        # AUTO: check model capabilities
        if self.model:
            return supports_structured_output(self.model)
        # Default router model - assume it supports structured output
        return True

    def _build_character_bio(self, character: Character) -> str:
        """Build character biography for system prompt.

        Args:
            character: Character object

        Returns:
            Formatted biography string
        """
        lines = []

        if character.historical_note:
            lines.append(f"HISTORICAL CONTEXT: {character.historical_note}")

        if character.personality:
            lines.append(f"PERSONALITY: {character.personality}")

        if character.speaking_style:
            lines.append(f"SPEAKING STYLE: {character.speaking_style}")

        if character.voice_notes:
            lines.append(f"VOICE: {character.voice_notes}")

        if character.emotional_state:
            lines.append(f"CURRENT EMOTIONAL STATE: {character.emotional_state}")

        if character.action:
            lines.append(f"CURRENT ACTION: {character.action}")

        if character.description:
            lines.append(f"APPEARANCE: {character.description}")

        return "\n".join(lines) if lines else "A character from this historical moment."

    def _format_history(
        self,
        history: list[ChatMessage],
    ) -> list[tuple[str, str]]:
        """Format chat history for prompts.

        Args:
            history: List of ChatMessage objects

        Returns:
            List of (role, content) tuples
        """
        formatted = []
        for msg in history:
            if msg.role == ChatRole.USER:
                formatted.append(("user", msg.content))
            elif msg.role == ChatRole.CHARACTER:
                formatted.append(("character", msg.content))
        return formatted

    async def chat(
        self,
        input_data: ChatInput,
        temperature: float = 0.8,
    ) -> AgentResult[ChatOutput]:
        """Generate a response from the character.

        Args:
            input_data: ChatInput with character and message
            temperature: LLM temperature for creativity

        Returns:
            AgentResult containing ChatOutput
        """
        start_time = time.perf_counter()

        try:
            # Build system prompt from character bio
            character_bio = self._build_character_bio(input_data.character)
            system_prompt = chat_prompts.get_chat_system_prompt(
                character_name=input_data.character.name,
                character_bio=character_bio,
                year=input_data.year,
                location=input_data.location,
                era=input_data.era,
                scene_context=input_data.scene_context,
            )

            # Build user prompt with history if available
            history_tuples = self._format_history(input_data.history)
            user_prompt = chat_prompts.get_chat_user_prompt(
                character_name=input_data.character.name,
                message=input_data.message,
                history=history_tuples if history_tuples else None,
            )

            # Combine prompts for the call
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            logger.debug(f"{self.name}: chatting with {input_data.character.name}")

            # Make LLM call
            response = await self.router.call(
                prompt=full_prompt,
                temperature=temperature,
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            # Parse response
            response_text = response.content.strip()

            # Clean up response - remove any accidental prefixes
            if response_text.lower().startswith(input_data.character.name.lower()):
                response_text = response_text[len(input_data.character.name):].lstrip(":").strip()

            # Detect emotional tone (simple heuristic)
            emotional_tone = self._detect_emotional_tone(response_text)

            output = ChatOutput(
                character_name=input_data.character.name,
                response=response_text,
                in_character=True,
                emotional_tone=emotional_tone,
            )

            logger.debug(f"{self.name}: completed in {latency}ms")

            return AgentResult(
                success=True,
                content=output,
                latency_ms=latency,
                model_used=response.model,
                metadata={
                    "character": input_data.character.name,
                    "history_length": len(input_data.history),
                    "model_override": self.model,
                    "response_format": self.response_format.value,
                    "used_structured": self._should_use_structured(),
                },
            )

        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)

            logger.error(f"{self.name}: failed - {error_msg}")

            return AgentResult(
                success=False,
                error=error_msg,
                latency_ms=latency,
            )

    async def chat_stream(
        self,
        input_data: ChatInput,
        temperature: float = 0.8,
    ) -> AsyncIterator[str]:
        """Stream a response from the character.

        Yields tokens as they are generated for real-time display.

        Args:
            input_data: ChatInput with character and message
            temperature: LLM temperature for creativity

        Yields:
            Token strings as they are generated
        """
        # Build prompts
        character_bio = self._build_character_bio(input_data.character)
        system_prompt = chat_prompts.get_chat_system_prompt(
            character_name=input_data.character.name,
            character_bio=character_bio,
            year=input_data.year,
            location=input_data.location,
            era=input_data.era,
            scene_context=input_data.scene_context,
        )

        history_tuples = self._format_history(input_data.history)
        user_prompt = chat_prompts.get_chat_user_prompt(
            character_name=input_data.character.name,
            message=input_data.message,
            history=history_tuples if history_tuples else None,
        )

        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        logger.debug(f"{self.name}: streaming chat with {input_data.character.name}")

        # Stream from router
        async for token in self.router.stream(
            prompt=full_prompt,
            temperature=temperature,
        ):
            yield token

    def _detect_emotional_tone(self, text: str) -> str | None:
        """Detect emotional tone from response text.

        Simple heuristic-based detection.

        Args:
            text: Response text

        Returns:
            Detected emotional tone or None
        """
        text_lower = text.lower()

        # Check for tone indicators
        if any(word in text_lower for word in ["alas", "sorrow", "grief", "sadly"]):
            return "melancholic"
        if any(word in text_lower for word in ["joy", "pleased", "delighted", "wonderful"]):
            return "joyful"
        if any(word in text_lower for word in ["anger", "furious", "outrage", "insolent"]):
            return "angry"
        if any(word in text_lower for word in ["worry", "concern", "fear", "anxious"]):
            return "anxious"
        if any(word in text_lower for word in ["curious", "wonder", "interesting", "intrigued"]):
            return "curious"
        if "!" in text and len(text) < 100:
            return "emphatic"

        return "neutral"


# =============================================================================
# IN-MEMORY SESSION MANAGER
# =============================================================================


class ChatSessionManager:
    """Manages in-memory chat sessions.

    Provides session storage for multi-turn conversations without
    database persistence.

    Attributes:
        sessions: Dictionary of session_id -> ChatSession
        max_sessions: Maximum number of sessions to keep

    Examples:
        >>> manager = ChatSessionManager()
        >>> session = manager.create_session("tp_123", "Benjamin Franklin")
        >>> manager.add_message(session.id, "user", "Hello!")
    """

    def __init__(self, max_sessions: int = 1000) -> None:
        """Initialize session manager.

        Args:
            max_sessions: Maximum sessions to keep in memory
        """
        self.sessions: dict[str, ChatSession] = {}
        self.max_sessions = max_sessions

    def create_session(
        self,
        timepoint_id: str,
        character_name: str,
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            timepoint_id: Associated timepoint ID
            character_name: Character being chatted with

        Returns:
            New ChatSession instance
        """
        # Clean up old sessions if needed
        if len(self.sessions) >= self.max_sessions:
            self._cleanup_oldest_sessions()

        session_id = str(uuid.uuid4())
        session = ChatSession(
            id=session_id,
            timepoint_id=timepoint_id,
            character_name=character_name,
            messages=[],
        )
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> ChatSession | None:
        """Get a session by ID.

        Args:
            session_id: Session ID to retrieve

        Returns:
            ChatSession or None if not found
        """
        return self.sessions.get(session_id)

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        character_name: str | None = None,
    ) -> bool:
        """Add a message to a session.

        Args:
            session_id: Session ID
            role: Message role (user/character)
            content: Message content
            character_name: Character name (for character messages)

        Returns:
            True if message was added, False if session not found
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        from datetime import datetime

        chat_role = ChatRole.USER if role == "user" else ChatRole.CHARACTER
        message = ChatMessage(
            role=chat_role,
            content=content,
            character_name=character_name,
            timestamp=datetime.utcnow(),
        )
        session.messages.append(message)
        session.updated_at = datetime.utcnow()
        return True

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

    def get_sessions_for_timepoint(
        self,
        timepoint_id: str,
    ) -> list[ChatSession]:
        """Get all sessions for a timepoint.

        Args:
            timepoint_id: Timepoint ID

        Returns:
            List of ChatSession objects
        """
        return [
            s for s in self.sessions.values()
            if s.timepoint_id == timepoint_id
        ]

    def _cleanup_oldest_sessions(self) -> None:
        """Remove oldest sessions to make room for new ones."""
        # Sort by updated_at and remove oldest 10%
        sorted_sessions = sorted(
            self.sessions.items(),
            key=lambda x: x[1].updated_at or x[1].created_at,
        )
        num_to_remove = max(1, len(sorted_sessions) // 10)
        for session_id, _ in sorted_sessions[:num_to_remove]:
            del self.sessions[session_id]


# Global session manager instance
_session_manager: ChatSessionManager | None = None


def get_session_manager() -> ChatSessionManager:
    """Get the global session manager instance.

    Returns:
        ChatSessionManager singleton
    """
    global _session_manager
    if _session_manager is None:
        _session_manager = ChatSessionManager()
    return _session_manager
