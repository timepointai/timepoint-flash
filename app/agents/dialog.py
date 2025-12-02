"""Dialog Agent for dialog generation.

The Dialog Agent creates up to 7 lines of period-appropriate dialog
for the characters in the scene.

Examples:
    >>> from app.agents.dialog import DialogAgent, DialogInput
    >>> agent = DialogAgent()
    >>> result = await agent.run(DialogInput(...))
    >>> for line in result.content.lines:
    ...     print(f"{line.speaker}: {line.text}")

Tests:
    - tests/unit/test_agents/test_dialog.py::test_dialog_max_seven
    - tests/unit/test_agents/test_dialog.py::test_dialog_period_appropriate
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent

logger = logging.getLogger(__name__)
from app.core.llm_router import LLMRouter
from app.prompts import dialog as dialog_prompts
from app.schemas import Character, CharacterData, DialogData, DialogLine, SceneData, TimelineData
from app.schemas.graph import GraphData, Relationship


@dataclass
class DialogInput:
    """Input data for Dialog Agent.

    Supports both batch and sequential (highly granular) dialog generation.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        speaking_characters: Full Character objects for sequential generation
        character_names: Character names for backwards compatibility
        relationships: Character relationships from Graph Agent (allies, rivals, etc.)
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    speaking_characters: list[Character] = field(default_factory=list)
    character_names: list[str] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    @classmethod
    def from_data(
        cls,
        query: str,
        timeline: TimelineData,
        scene: SceneData,
        characters: CharacterData,
        graph: GraphData | None = None,
    ) -> "DialogInput":
        """Create DialogInput from previous agent data.

        Args:
            query: Original/cleaned query
            timeline: TimelineData from Timeline Agent
            scene: SceneData from Scene Agent
            characters: CharacterData from Characters Agent
            graph: GraphData from Graph Agent (optional but recommended!)

        Returns:
            DialogInput populated with context including full Character objects
        """
        # Get speaking characters (full Character objects)
        speaking_chars = list(characters.speaking_characters)
        # If none marked, use primary/secondary
        if not speaking_chars:
            speaking_chars = list(characters.primary_characters[:2])
            speaking_chars.extend(characters.secondary_characters[:2])

        # Limit to max 4 speakers for dialog coherence
        speaking_chars = speaking_chars[:4]

        # Get names for backwards compatibility
        speaking_names = [c.name for c in speaking_chars]

        # Get relationships if graph data provided
        relationships = graph.relationships if graph else []

        return cls(
            query=query,
            year=timeline.year,
            era=timeline.era,
            location=timeline.location,
            setting=scene.setting,
            atmosphere=scene.atmosphere,
            tension_level=scene.tension_level,
            speaking_characters=speaking_chars,
            character_names=speaking_names,
            relationships=relationships,
        )

    def get_relationship(self, char1: str, char2: str) -> Relationship | None:
        """Get the relationship between two characters.

        Args:
            char1: First character name
            char2: Second character name

        Returns:
            Relationship if found, None otherwise
        """
        for rel in self.relationships:
            if (rel.from_character.lower() == char1.lower() and
                rel.to_character.lower() == char2.lower()) or \
               (rel.from_character.lower() == char2.lower() and
                rel.to_character.lower() == char1.lower()):
                return rel
        return None

    def get_relationship_context(self, char1: str, char2: str) -> str:
        """Get a text description of the relationship for prompts.

        Args:
            char1: First character name
            char2: Second character name

        Returns:
            Description string, or empty if no relationship
        """
        rel = self.get_relationship(char1, char2)
        if not rel:
            return ""
        return f"{char1} and {char2} are {rel.relationship_type}s. {rel.description}"


class DialogAgent(BaseAgent[DialogInput, DialogData]):
    """Agent that generates dialog for the scene using sequential roleplay.

    Uses HIGHLY GRANULAR dialog generation: each line is generated separately
    with the character's bio as the system prompt. The LLM "becomes" each
    character in turn, generating authentic, personality-driven dialog.

    Attributes:
        response_model: DialogData Pydantic model
        name: "DialogAgent"
        max_lines: Maximum dialog lines (default 7)
        use_sequential: Whether to use sequential generation (default True)

    Dialog Flow:
        1. First speaker's bio becomes system prompt
        2. LLM generates one line as that character
        3. Next speaker's bio becomes system prompt
        4. LLM sees conversation history + responds in character
        5. Repeat up to max_lines

    Examples:
        >>> agent = DialogAgent()
        >>> result = await agent.run(DialogInput(
        ...     query="signing of the declaration",
        ...     year=1776,
        ...     speaking_characters=[char1, char2]  # Full Character objects
        ... ))
        >>> len(result.content.lines)  # <= 7

    Tests:
        - tests/unit/test_agents/test_dialog.py::test_dialog_initialization
        - tests/unit/test_agents/test_dialog.py::test_dialog_run
    """

    response_model = DialogData

    def __init__(
        self,
        router: LLMRouter | None = None,
        max_lines: int = 7,
        use_sequential: bool = True,
    ) -> None:
        """Initialize Dialog Agent.

        Args:
            router: LLM router for API calls
            max_lines: Maximum dialog lines to generate (default 7)
            use_sequential: Use sequential roleplay generation (default True)
        """
        super().__init__(router=router, name="DialogAgent")
        self.max_lines = max_lines
        self.use_sequential = use_sequential

    def get_system_prompt(self) -> str:
        """Get the system prompt for batch dialog generation."""
        return dialog_prompts.get_system_prompt()

    def get_prompt(self, input_data: DialogInput) -> str:
        """Get the user prompt for batch dialog generation."""
        # Build character context from full Character objects if available
        context_parts = []
        character_names = input_data.character_names or []

        if self._has_full_character_objects(input_data):
            for char in input_data.speaking_characters:
                context_parts.append(char.to_dialog_context())
            if not character_names:
                character_names = [c.name for c in input_data.speaking_characters]
        else:
            # Legacy mode: speaking_characters might be strings
            for char in input_data.speaking_characters:
                if isinstance(char, str):
                    context_parts.append(f"- {char}")
                    if char not in character_names:
                        character_names.append(char)

        character_context = "\n\n".join(context_parts)

        return dialog_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            speaking_characters=character_names,
            character_context=character_context,
        )

    async def _generate_single_line(
        self,
        character: Character,
        input_data: DialogInput,
        conversation_history: list[tuple[str, str]],
        is_first_turn: bool,
        last_speaker: str | None,
        last_line: str | None,
    ) -> str | None:
        """Generate a single dialog line for one character.

        Uses the character's bio as the system prompt for authentic roleplay.

        Args:
            character: The Character object (their bio becomes system prompt)
            input_data: Full dialog input context
            conversation_history: List of (speaker, text) tuples so far
            is_first_turn: Whether this is the first line of dialog
            last_speaker: Name of the previous speaker
            last_line: Text of the previous line

        Returns:
            The generated dialog text, or None if generation failed
        """
        # Character bio becomes the system prompt
        system_prompt = character.to_system_prompt(
            year=input_data.year,
            location=input_data.location,
            era=input_data.era,
        )

        # Build user prompt based on conversation state
        if is_first_turn:
            user_prompt = dialog_prompts.get_sequential_first_turn_prompt(
                query=input_data.query,
                setting=input_data.setting,
                atmosphere=input_data.atmosphere,
                tension_level=input_data.tension_level,
            )
        else:
            history_str = dialog_prompts.format_conversation_history(conversation_history)
            user_prompt = dialog_prompts.get_sequential_response_prompt(
                conversation_history=history_str,
                other_character=last_speaker or "Someone",
                last_line=last_line or "",
            )

        # Call LLM with character roleplay prompt
        # Combine system and user prompts into a single prompt
        combined_prompt = f"""{system_prompt}

---

{user_prompt}"""

        try:
            response = await self.router.call(
                prompt=combined_prompt,
                temperature=0.85,  # Slightly higher for creative dialog
            )

            # Clean up the response - remove quotes, names, stage directions
            text = response.content.strip()
            # Remove leading character name if present
            if text.lower().startswith(character.name.lower()):
                text = text[len(character.name):].lstrip(":").strip()
            # Remove surrounding quotes
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            if text.startswith("'") and text.endswith("'"):
                text = text[1:-1]

            return text if text else None

        except Exception as e:
            logger.warning(f"Failed to generate line for {character.name}: {e}")
            return None

    def _pick_next_speaker(
        self,
        characters: list[Character],
        conversation_history: list[tuple[str, str]],
        line_index: int,
    ) -> Character:
        """Pick the next character to speak.

        Uses a pattern that creates natural back-and-forth dialog:
        - Line 0: First character (usually most important)
        - Line 1: Second character (response)
        - Lines 2+: Alternate with occasional third speaker

        Args:
            characters: Available speaking characters
            conversation_history: Dialog so far
            line_index: Current line number (0-indexed)

        Returns:
            The Character who should speak next
        """
        if not characters:
            raise ValueError("No speaking characters available")

        num_chars = len(characters)

        if num_chars == 1:
            return characters[0]

        if num_chars == 2:
            # Simple alternation
            return characters[line_index % 2]

        # For 3+ characters, use weighted selection
        # Primary pattern: char0, char1, char0, char1, char2, char0, char1...
        if line_index < 4:
            return characters[line_index % 2]
        elif line_index == 4 and num_chars > 2:
            return characters[2]  # Third character gets a turn
        else:
            return characters[line_index % 2]

    async def _run_sequential(self, input_data: DialogInput) -> AgentResult[DialogData]:
        """Generate dialog using sequential roleplay.

        Each character's bio becomes the system prompt for their line.

        Args:
            input_data: DialogInput with full Character objects

        Returns:
            AgentResult containing DialogData with generated lines
        """
        import time
        start_time = time.time()

        characters = input_data.speaking_characters
        if not characters:
            return AgentResult(
                success=False,
                content=None,
                error="No speaking characters provided",
                metadata={"generation_mode": "sequential"},
            )

        lines: list[DialogLine] = []
        conversation_history: list[tuple[str, str]] = []
        last_speaker: str | None = None
        last_line: str | None = None

        for i in range(self.max_lines):
            # Pick next speaker
            speaker = self._pick_next_speaker(characters, conversation_history, i)

            # Generate their line
            text = await self._generate_single_line(
                character=speaker,
                input_data=input_data,
                conversation_history=conversation_history,
                is_first_turn=(i == 0),
                last_speaker=last_speaker,
                last_line=last_line,
            )

            if not text:
                # If generation failed, try to continue with next speaker
                continue

            # Create dialog line
            dialog_line = DialogLine(
                speaker=speaker.name,
                text=text,
                tone=speaker.emotional_state,  # Use character's emotional state as tone
            )
            lines.append(dialog_line)

            # Update history for next iteration
            conversation_history.append((speaker.name, text))
            last_speaker = speaker.name
            last_line = text

            # Stop if we have enough good lines
            if len(lines) >= self.max_lines:
                break

        elapsed_ms = int((time.time() - start_time) * 1000)

        if not lines:
            return AgentResult(
                success=False,
                content=None,
                error="Failed to generate any dialog lines",
                latency_ms=elapsed_ms,
                metadata={"generation_mode": "sequential"},
            )

        # Build DialogData
        dialog_data = DialogData(
            lines=lines,
            scene_context=f"{input_data.setting} - {input_data.atmosphere}",
            language_style=f"Period-appropriate for {input_data.year} {input_data.era or ''}".strip(),
        )

        return AgentResult(
            success=True,
            content=dialog_data,
            latency_ms=elapsed_ms,
            metadata={
                "generation_mode": "sequential",
                "line_count": len(lines),
                "speakers": list(set(line.speaker for line in lines)),
                "llm_calls": len(lines),
            },
        )

    def _has_full_character_objects(self, input_data: DialogInput) -> bool:
        """Check if speaking_characters contains Character objects (not strings)."""
        if not input_data.speaking_characters:
            return False
        # Check the first item - if it's a string, we're in legacy mode
        first = input_data.speaking_characters[0]
        return hasattr(first, "to_system_prompt")

    async def run(self, input_data: DialogInput) -> AgentResult[DialogData]:
        """Generate dialog for the scene.

        Uses sequential roleplay generation by default when full Character
        objects are available. Falls back to batch generation for legacy
        string-only character names.

        Args:
            input_data: DialogInput with context and Character objects

        Returns:
            AgentResult containing DialogData
        """
        # Use sequential generation only if we have full Character objects
        if self.use_sequential and self._has_full_character_objects(input_data):
            return await self._run_sequential(input_data)

        # Fallback to batch generation (for legacy string-only mode)
        result = await self._call_llm(input_data, temperature=0.8)

        if result.success and result.content:
            result.metadata["generation_mode"] = "batch"
            result.metadata["line_count"] = result.content.line_count
            result.metadata["speakers"] = result.content.speakers

        return result
