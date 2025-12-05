"""Dialog Extension Agent for generating more dialog.

Extends existing dialog in a timepoint with additional lines,
either continuing the conversation or taking a new direction.

Examples:
    >>> from app.agents.dialog_extension import DialogExtensionAgent, DialogExtensionInput
    >>> agent = DialogExtensionAgent()
    >>> result = await agent.extend(input_data)
    >>> for line in result.content.dialog:
    ...     print(f"{line['speaker']}: {line['text']}")

Tests:
    - tests/unit/test_agents/test_dialog_extension.py
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from pydantic import BaseModel, Field

from app.agents.base import AgentResult
from app.core.llm_router import LLMRouter
from app.core.model_capabilities import (
    infer_provider_from_model_id,
    supports_structured_output,
)
from app.prompts import character_chat as chat_prompts
from app.schemas import Character, CharacterData, DialogData, DialogLine
from app.schemas.chat import DialogExtensionResponse, ResponseFormat

logger = logging.getLogger(__name__)


# =============================================================================
# INPUT/OUTPUT SCHEMAS
# =============================================================================


@dataclass
class DialogExtensionInput:
    """Input for dialog extension.

    Attributes:
        characters: Characters available for dialog
        existing_dialog: Current dialog lines
        year: Scene year
        location: Scene location
        era: Historical era
        setting: Scene setting description
        atmosphere: Scene atmosphere
        num_lines: Number of new lines to generate
        prompt: Optional user direction
        selected_characters: Optional subset of characters to include
    """

    characters: list[Character]
    existing_dialog: list[DialogLine]
    year: int
    location: str
    era: str | None = None
    setting: str = ""
    atmosphere: str = ""
    num_lines: int = 5
    prompt: str | None = None
    selected_characters: list[str] | None = None

    @classmethod
    def from_timepoint_data(
        cls,
        characters: CharacterData | list[Character],
        existing_dialog: DialogData | list[DialogLine] | None,
        year: int,
        location: str,
        era: str | None = None,
        setting: str = "",
        atmosphere: str = "",
        num_lines: int = 5,
        prompt: str | None = None,
        selected_characters: list[str] | None = None,
    ) -> "DialogExtensionInput":
        """Create input from timepoint data.

        Args:
            characters: CharacterData or list of Character objects
            existing_dialog: Existing DialogData or list of DialogLine
            year: Scene year
            location: Scene location
            era: Historical era
            setting: Scene setting
            atmosphere: Scene atmosphere
            num_lines: Number of lines to generate
            prompt: Optional user direction
            selected_characters: Optional character filter

        Returns:
            DialogExtensionInput instance
        """
        # Handle CharacterData or list
        if isinstance(characters, CharacterData):
            char_list = characters.characters
        else:
            char_list = characters

        # Handle DialogData or list
        if existing_dialog is None:
            dialog_list = []
        elif isinstance(existing_dialog, DialogData):
            dialog_list = existing_dialog.lines
        else:
            dialog_list = existing_dialog

        return cls(
            characters=char_list,
            existing_dialog=dialog_list,
            year=year,
            location=location,
            era=era,
            setting=setting,
            atmosphere=atmosphere,
            num_lines=num_lines,
            prompt=prompt,
            selected_characters=selected_characters,
        )


# =============================================================================
# DIALOG EXTENSION AGENT
# =============================================================================


class DialogExtensionAgent:
    """Agent for generating additional dialog lines.

    Can continue existing dialog or generate new exchanges based on
    user direction. Uses sequential roleplay for authentic character voices.

    Attributes:
        router: LLM router for API calls
        name: Agent name for logging
        model: Optional model override
        response_format: Response format preference

    Examples:
        >>> agent = DialogExtensionAgent()
        >>> input_data = DialogExtensionInput(
        ...     characters=[char1, char2],
        ...     existing_dialog=existing_lines,
        ...     year=1776,
        ...     location="Philadelphia"
        ... )
        >>> result = await agent.extend(input_data)

    Tests:
        - tests/unit/test_agents/test_dialog_extension.py::test_extend_basic
    """

    def __init__(
        self,
        router: LLMRouter | None = None,
        name: str = "DialogExtensionAgent",
        model: str | None = None,
        response_format: ResponseFormat = ResponseFormat.AUTO,
    ) -> None:
        """Initialize Dialog Extension Agent.

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

    def _filter_characters(
        self,
        characters: list[Character],
        selected_names: list[str] | None,
    ) -> list[Character]:
        """Filter characters to include in dialog.

        Args:
            characters: All available characters
            selected_names: Names to include (None = all)

        Returns:
            Filtered list of characters
        """
        if selected_names is None:
            # Use speaking characters or primary/secondary
            speaking = [c for c in characters if c.speaks_in_scene]
            if speaking:
                return speaking[:4]  # Max 4 speakers

            # Fallback to primary + secondary
            result = []
            for c in characters:
                if c.role.value in ("primary", "secondary"):
                    result.append(c)
                    if len(result) >= 4:
                        break
            return result if result else characters[:2]

        # Filter by names
        selected_lower = [n.lower() for n in selected_names]
        return [c for c in characters if c.name.lower() in selected_lower]

    def _format_existing_dialog(
        self,
        dialog: list[DialogLine],
    ) -> str:
        """Format existing dialog for prompt.

        Args:
            dialog: List of DialogLine objects

        Returns:
            Formatted dialog string
        """
        if not dialog:
            return "(No previous dialog)"

        lines = []
        for line in dialog:
            tone_str = f" [{line.tone}]" if line.tone else ""
            lines.append(f"{line.speaker}{tone_str}: \"{line.text}\"")
        return "\n".join(lines)

    def _format_character_profiles(
        self,
        characters: list[Character],
    ) -> str:
        """Format character profiles for prompt.

        Args:
            characters: List of Character objects

        Returns:
            Formatted profiles string
        """
        profiles = []
        for char in characters:
            profiles.append(char.to_dialog_context())
        return "\n\n".join(profiles)

    async def extend(
        self,
        input_data: DialogExtensionInput,
        temperature: float = 0.85,
    ) -> AgentResult[DialogExtensionResponse]:
        """Generate additional dialog lines.

        Args:
            input_data: DialogExtensionInput with context
            temperature: LLM temperature for creativity

        Returns:
            AgentResult containing DialogExtensionResponse
        """
        start_time = time.perf_counter()

        try:
            # Filter characters
            active_chars = self._filter_characters(
                input_data.characters,
                input_data.selected_characters,
            )

            if not active_chars:
                return AgentResult(
                    success=False,
                    error="No characters available for dialog",
                    latency_ms=0,
                )

            # Format prompts
            existing_dialog_str = self._format_existing_dialog(input_data.existing_dialog)
            character_profiles = self._format_character_profiles(active_chars)

            prompt = chat_prompts.get_dialog_extension_prompt(
                location=input_data.location,
                year=input_data.year,
                era=input_data.era,
                setting=input_data.setting,
                atmosphere=input_data.atmosphere,
                character_profiles=character_profiles,
                existing_dialog=existing_dialog_str,
                num_lines=input_data.num_lines,
                prompt=input_data.prompt,
            )

            logger.debug(f"{self.name}: generating {input_data.num_lines} dialog lines")

            # Make structured LLM call
            response = await self.router.call_structured(
                prompt=prompt,
                response_model=DialogExtensionResponse,
                temperature=temperature,
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            # Get characters who spoke
            characters_involved = list(set(
                line.get("speaker", "") for line in response.content.dialog
            ))

            # Update response with characters
            result_content = DialogExtensionResponse(
                dialog=response.content.dialog,
                context=response.content.context,
                characters_involved=characters_involved,
            )

            logger.debug(f"{self.name}: completed in {latency}ms with {len(result_content.dialog)} lines")

            return AgentResult(
                success=True,
                content=result_content,
                latency_ms=latency,
                model_used=response.model,
                metadata={
                    "lines_generated": len(result_content.dialog),
                    "characters": characters_involved,
                    "had_existing_dialog": bool(input_data.existing_dialog),
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

    async def extend_sequential(
        self,
        input_data: DialogExtensionInput,
        temperature: float = 0.85,
    ) -> AgentResult[DialogExtensionResponse]:
        """Generate dialog using sequential roleplay.

        Each character's bio becomes the system prompt for their line,
        producing more authentic character voices.

        Args:
            input_data: DialogExtensionInput with context
            temperature: LLM temperature

        Returns:
            AgentResult containing DialogExtensionResponse
        """
        start_time = time.perf_counter()

        try:
            # Filter characters
            active_chars = self._filter_characters(
                input_data.characters,
                input_data.selected_characters,
            )

            if not active_chars:
                return AgentResult(
                    success=False,
                    error="No characters available for dialog",
                    latency_ms=0,
                )

            # Build conversation history from existing dialog
            conversation_history: list[tuple[str, str]] = [
                (line.speaker, line.text) for line in input_data.existing_dialog
            ]

            new_lines: list[dict[str, Any]] = []
            last_speaker: str | None = None
            last_text: str | None = None

            if conversation_history:
                last_speaker, last_text = conversation_history[-1]

            # Generate each line sequentially
            for i in range(input_data.num_lines):
                # Pick next speaker (rotate through characters)
                speaker_idx = i % len(active_chars)
                speaker = active_chars[speaker_idx]

                # Skip if same as last speaker (try next)
                if last_speaker and speaker.name == last_speaker and len(active_chars) > 1:
                    speaker_idx = (speaker_idx + 1) % len(active_chars)
                    speaker = active_chars[speaker_idx]

                # Build system prompt from character bio
                system_prompt = speaker.to_system_prompt(
                    year=input_data.year,
                    location=input_data.location,
                    era=input_data.era,
                )

                # Build user prompt based on context
                if not conversation_history and not new_lines:
                    # First line ever
                    user_prompt = f"""You are in this scene:
Setting: {input_data.setting}
Atmosphere: {input_data.atmosphere}
{f'Direction: {input_data.prompt}' if input_data.prompt else ''}

What do you say? Give ONLY your spoken words (1-2 sentences).
Do NOT include your name, quotation marks, or stage directions."""
                else:
                    # Continuing conversation
                    history_str = "\n".join(
                        f'{s}: "{t}"' for s, t in conversation_history
                    )
                    for line in new_lines:
                        history_str += f'\n{line["speaker"]}: "{line["text"]}"'

                    user_prompt = f"""The conversation so far:
{history_str}

{last_speaker or 'Someone'} just said: "{last_text or ''}"
{f'Direction: {input_data.prompt}' if input_data.prompt else ''}

What do you say in response? Give ONLY your spoken words (1-2 sentences).
Do NOT include your name, quotation marks, or stage directions."""

                # Combine prompts
                full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

                # Generate line
                response = await self.router.call(
                    prompt=full_prompt,
                    temperature=temperature,
                )

                # Clean response
                text = response.content.strip()
                if text.lower().startswith(speaker.name.lower()):
                    text = text[len(speaker.name):].lstrip(":").strip()
                if text.startswith('"') and text.endswith('"'):
                    text = text[1:-1]
                if text.startswith("'") and text.endswith("'"):
                    text = text[1:-1]

                if text:
                    new_lines.append({
                        "speaker": speaker.name,
                        "text": text,
                        "tone": speaker.emotional_state,
                    })
                    last_speaker = speaker.name
                    last_text = text

            latency = int((time.perf_counter() - start_time) * 1000)

            if not new_lines:
                return AgentResult(
                    success=False,
                    error="Failed to generate any dialog lines",
                    latency_ms=latency,
                )

            characters_involved = list(set(line["speaker"] for line in new_lines))

            result = DialogExtensionResponse(
                dialog=new_lines,
                context=f"Continued dialog in {input_data.setting}",
                characters_involved=characters_involved,
            )

            logger.debug(f"{self.name}: sequential generation completed in {latency}ms")

            return AgentResult(
                success=True,
                content=result,
                latency_ms=latency,
                metadata={
                    "lines_generated": len(new_lines),
                    "characters": characters_involved,
                    "generation_mode": "sequential",
                    "llm_calls": len(new_lines),
                },
            )

        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            error_msg = str(e)

            logger.error(f"{self.name}: sequential generation failed - {error_msg}")

            return AgentResult(
                success=False,
                error=error_msg,
                latency_ms=latency,
            )

    async def extend_stream(
        self,
        input_data: DialogExtensionInput,
        temperature: float = 0.85,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream dialog generation line by line.

        Yields each line as it's generated for real-time display.

        Args:
            input_data: DialogExtensionInput with context
            temperature: LLM temperature

        Yields:
            Dict with line data: {"speaker": ..., "text": ..., "line_number": ...}
        """
        # Filter characters
        active_chars = self._filter_characters(
            input_data.characters,
            input_data.selected_characters,
        )

        if not active_chars:
            yield {"error": "No characters available for dialog"}
            return

        # Build conversation history
        conversation_history: list[tuple[str, str]] = [
            (line.speaker, line.text) for line in input_data.existing_dialog
        ]

        last_speaker: str | None = None
        last_text: str | None = None

        if conversation_history:
            last_speaker, last_text = conversation_history[-1]

        generated_lines: list[tuple[str, str]] = []

        for i in range(input_data.num_lines):
            # Pick speaker
            speaker_idx = i % len(active_chars)
            speaker = active_chars[speaker_idx]

            if last_speaker and speaker.name == last_speaker and len(active_chars) > 1:
                speaker_idx = (speaker_idx + 1) % len(active_chars)
                speaker = active_chars[speaker_idx]

            # Build prompts (same as extend_sequential)
            system_prompt = speaker.to_system_prompt(
                year=input_data.year,
                location=input_data.location,
                era=input_data.era,
            )

            if not conversation_history and not generated_lines:
                user_prompt = f"""You are in this scene:
Setting: {input_data.setting}
Atmosphere: {input_data.atmosphere}
{f'Direction: {input_data.prompt}' if input_data.prompt else ''}

What do you say? Give ONLY your spoken words (1-2 sentences)."""
            else:
                history_str = "\n".join(
                    f'{s}: "{t}"' for s, t in conversation_history
                )
                for s, t in generated_lines:
                    history_str += f'\n{s}: "{t}"'

                user_prompt = f"""The conversation so far:
{history_str}

{last_speaker or 'Someone'} just said: "{last_text or ''}"
{f'Direction: {input_data.prompt}' if input_data.prompt else ''}

What do you say in response? Give ONLY your spoken words (1-2 sentences)."""

            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            # Generate and yield
            response = await self.router.call(
                prompt=full_prompt,
                temperature=temperature,
            )

            text = response.content.strip()
            if text.lower().startswith(speaker.name.lower()):
                text = text[len(speaker.name):].lstrip(":").strip()
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]

            if text:
                generated_lines.append((speaker.name, text))
                last_speaker = speaker.name
                last_text = text

                yield {
                    "speaker": speaker.name,
                    "text": text,
                    "tone": speaker.emotional_state,
                    "line_number": i + 1,
                }

        # Final done event
        yield {
            "done": True,
            "total_lines": len(generated_lines),
            "characters_involved": list(set(s for s, _ in generated_lines)),
        }
