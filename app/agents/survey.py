"""Survey Agent for asking questions to multiple characters.

Enables survey-style questioning of characters from timepoint scenes,
with support for parallel or sequential execution and response analysis.

Examples:
    >>> from app.agents.survey import SurveyAgent, SurveyInput
    >>> agent = SurveyAgent()
    >>> result = await agent.survey(input_data)
    >>> for resp in result.content.responses:
    ...     print(f"{resp.character_name}: {resp.response}")

Tests:
    - tests/unit/test_agents/test_survey.py
"""

from __future__ import annotations

import asyncio
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
from app.schemas import Character, CharacterData
from app.schemas.chat import (
    CharacterSurveyResponse,
    ResponseFormat,
    SurveyMode,
    SurveyResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# INPUT SCHEMA
# =============================================================================


@dataclass
class SurveyInput:
    """Input for character survey.

    Attributes:
        characters: Characters to survey
        questions: Questions to ask
        year: Scene year
        location: Scene location
        era: Historical era
        mode: Execution mode (parallel/sequential)
        chain_prompts: Whether to share responses in sequential mode
        include_summary: Whether to generate a summary
    """

    characters: list[Character]
    questions: list[str]
    year: int
    location: str
    era: str | None = None
    mode: SurveyMode = SurveyMode.PARALLEL
    chain_prompts: bool = False
    include_summary: bool = True

    @classmethod
    def from_timepoint_data(
        cls,
        characters: CharacterData | list[Character],
        questions: list[str],
        year: int,
        location: str,
        era: str | None = None,
        mode: SurveyMode = SurveyMode.PARALLEL,
        chain_prompts: bool = False,
        include_summary: bool = True,
        selected_characters: list[str] | None = None,
    ) -> "SurveyInput":
        """Create input from timepoint data.

        Args:
            characters: CharacterData or list of Character objects
            questions: Questions to ask
            year: Scene year
            location: Scene location
            era: Historical era
            mode: Execution mode
            chain_prompts: Share responses in sequential mode
            include_summary: Generate summary
            selected_characters: Filter to specific characters

        Returns:
            SurveyInput instance
        """
        # Handle CharacterData or list
        if isinstance(characters, CharacterData):
            char_list = characters.characters
        else:
            char_list = characters

        # Filter if specified
        if selected_characters:
            selected_lower = [n.lower() for n in selected_characters]
            char_list = [c for c in char_list if c.name.lower() in selected_lower]

        return cls(
            characters=char_list,
            questions=questions,
            year=year,
            location=location,
            era=era,
            mode=mode,
            chain_prompts=chain_prompts,
            include_summary=include_summary,
        )


# =============================================================================
# SURVEY AGENT
# =============================================================================


class SurveyAgent:
    """Agent for surveying multiple characters with questions.

    Supports parallel execution (faster) or sequential execution
    (context-aware with optional response chaining).

    Attributes:
        router: LLM router for API calls
        name: Agent name for logging
        model: Optional model override
        response_format: Response format preference

    Examples:
        >>> agent = SurveyAgent()
        >>> input_data = SurveyInput(
        ...     characters=[ben_franklin, john_adams],
        ...     questions=["How do you feel about independence?"],
        ...     year=1776,
        ...     location="Philadelphia"
        ... )
        >>> result = await agent.survey(input_data)

    Tests:
        - tests/unit/test_agents/test_survey.py::test_survey_parallel
        - tests/unit/test_agents/test_survey.py::test_survey_sequential
    """

    def __init__(
        self,
        router: LLMRouter | None = None,
        name: str = "SurveyAgent",
        model: str | None = None,
        response_format: ResponseFormat = ResponseFormat.AUTO,
    ) -> None:
        """Initialize Survey Agent.

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

    def _build_character_bio(self, character: Character) -> str:
        """Build character biography for system prompt."""
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

        return "\n".join(lines) if lines else "A character from this historical moment."

    async def _ask_single_character(
        self,
        character: Character,
        question: str,
        year: int,
        location: str,
        era: str | None,
        prior_responses: list[tuple[str, str]] | None = None,
        temperature: float = 0.7,
    ) -> CharacterSurveyResponse:
        """Ask a single character a question.

        Args:
            character: Character to ask
            question: The question
            year: Scene year
            location: Scene location
            era: Historical era
            prior_responses: Previous responses (for chained surveys)
            temperature: LLM temperature

        Returns:
            CharacterSurveyResponse with the answer
        """
        # Build prompts
        character_bio = self._build_character_bio(character)
        system_prompt = chat_prompts.get_survey_system_prompt(
            character_name=character.name,
            character_bio=character_bio,
            year=year,
            location=location,
            era=era,
        )

        user_prompt = chat_prompts.get_survey_user_prompt(
            character_name=character.name,
            question=question,
            prior_responses=prior_responses,
        )

        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

        # Make LLM call
        response = await self.router.call(
            prompt=full_prompt,
            temperature=temperature,
        )

        response_text = response.content.strip()

        # Clean up response
        if response_text.lower().startswith(character.name.lower()):
            response_text = response_text[len(character.name):].lstrip(":").strip()

        # Analyze response
        sentiment = self._analyze_sentiment(response_text)
        key_points = self._extract_key_points(response_text)
        emotional_tone = self._detect_emotional_tone(response_text)

        return CharacterSurveyResponse(
            character_name=character.name,
            question=question,
            response=response_text,
            sentiment=sentiment,
            key_points=key_points,
            emotional_tone=emotional_tone,
        )

    def _analyze_sentiment(self, text: str) -> str:
        """Analyze sentiment of response text.

        Simple heuristic-based analysis.

        Args:
            text: Response text

        Returns:
            Sentiment label (positive/negative/neutral/mixed)
        """
        text_lower = text.lower()

        positive_words = ["agree", "support", "pleased", "excellent", "wonderful", "hope", "joy", "proud", "honor"]
        negative_words = ["disagree", "oppose", "concerned", "worried", "fear", "doubt", "unfortunately", "grave"]

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        if pos_count > 0 and neg_count > 0:
            return "mixed"
        elif pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"

    def _extract_key_points(self, text: str) -> list[str]:
        """Extract key points from response.

        Simple extraction based on sentence structure.

        Args:
            text: Response text

        Returns:
            List of key points
        """
        # Split into sentences
        sentences = text.replace("!", ".").replace("?", ".").split(".")
        sentences = [s.strip() for s in sentences if s.strip()]

        # Return first 2-3 sentences as key points
        return sentences[:3]

    def _detect_emotional_tone(self, text: str) -> str | None:
        """Detect emotional tone from response."""
        text_lower = text.lower()

        if any(w in text_lower for w in ["passion", "fervent", "zealous"]):
            return "passionate"
        if any(w in text_lower for w in ["concern", "worry", "grave"]):
            return "concerned"
        if any(w in text_lower for w in ["hope", "optimist", "believe"]):
            return "hopeful"
        if any(w in text_lower for w in ["resign", "accept", "inevitable"]):
            return "resigned"
        if any(w in text_lower for w in ["anger", "outrage", "fury"]):
            return "angry"

        return "thoughtful"

    async def _generate_summary(
        self,
        question: str,
        responses: list[tuple[str, str]],
    ) -> str:
        """Generate a summary of survey responses.

        Args:
            question: The question asked
            responses: List of (character_name, response) tuples

        Returns:
            Summary string
        """
        prompt = chat_prompts.get_survey_summary_prompt(question, responses)

        response = await self.router.call(
            prompt=prompt,
            temperature=0.5,  # Lower for more consistent summaries
        )

        return response.content.strip()

    async def survey(
        self,
        input_data: SurveyInput,
        temperature: float = 0.7,
    ) -> AgentResult[SurveyResult]:
        """Execute survey across characters.

        Args:
            input_data: SurveyInput with questions and characters
            temperature: LLM temperature

        Returns:
            AgentResult containing SurveyResult
        """
        start_time = time.perf_counter()

        try:
            if not input_data.characters:
                return AgentResult(
                    success=False,
                    error="No characters to survey",
                    latency_ms=0,
                )

            if not input_data.questions:
                return AgentResult(
                    success=False,
                    error="No questions to ask",
                    latency_ms=0,
                )

            all_responses: list[CharacterSurveyResponse] = []

            if input_data.mode == SurveyMode.PARALLEL:
                # Parallel execution
                all_responses = await self._survey_parallel(
                    input_data, temperature
                )
            else:
                # Sequential execution
                all_responses = await self._survey_sequential(
                    input_data, temperature
                )

            # Generate summary if requested
            summary: str | None = None
            if input_data.include_summary and all_responses:
                # Create summary for each question
                summaries = []
                for question in input_data.questions:
                    q_responses = [
                        (r.character_name, r.response)
                        for r in all_responses
                        if r.question == question
                    ]
                    if q_responses:
                        q_summary = await self._generate_summary(question, q_responses)
                        summaries.append(f"Q: {question}\n{q_summary}")

                summary = "\n\n".join(summaries)

            latency = int((time.perf_counter() - start_time) * 1000)

            result = SurveyResult(
                timepoint_id="",  # Will be set by API layer
                questions=input_data.questions,
                responses=all_responses,
                summary=summary,
                mode=input_data.mode,
                total_characters=len(input_data.characters),
            )

            logger.debug(f"{self.name}: completed with {len(all_responses)} responses in {latency}ms")

            return AgentResult(
                success=True,
                content=result,
                latency_ms=latency,
                metadata={
                    "total_responses": len(all_responses),
                    "characters_surveyed": len(input_data.characters),
                    "questions_asked": len(input_data.questions),
                    "mode": input_data.mode.value,
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

    async def _survey_parallel(
        self,
        input_data: SurveyInput,
        temperature: float,
    ) -> list[CharacterSurveyResponse]:
        """Execute survey in parallel (all at once).

        Args:
            input_data: Survey input
            temperature: LLM temperature

        Returns:
            List of all responses
        """
        tasks = []

        for character in input_data.characters:
            for question in input_data.questions:
                task = self._ask_single_character(
                    character=character,
                    question=question,
                    year=input_data.year,
                    location=input_data.location,
                    era=input_data.era,
                    prior_responses=None,
                    temperature=temperature,
                )
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        responses = []
        for result in results:
            if isinstance(result, CharacterSurveyResponse):
                responses.append(result)
            elif isinstance(result, Exception):
                logger.warning(f"Survey task failed: {result}")

        return responses

    async def _survey_sequential(
        self,
        input_data: SurveyInput,
        temperature: float,
    ) -> list[CharacterSurveyResponse]:
        """Execute survey sequentially (one at a time).

        Optionally shares prior responses with subsequent characters.

        Args:
            input_data: Survey input
            temperature: LLM temperature

        Returns:
            List of all responses
        """
        all_responses: list[CharacterSurveyResponse] = []

        for question in input_data.questions:
            question_responses: list[tuple[str, str]] = []

            for character in input_data.characters:
                # Get prior responses if chaining
                prior = question_responses if input_data.chain_prompts else None

                response = await self._ask_single_character(
                    character=character,
                    question=question,
                    year=input_data.year,
                    location=input_data.location,
                    era=input_data.era,
                    prior_responses=prior,
                    temperature=temperature,
                )

                all_responses.append(response)
                question_responses.append((character.name, response.response))

        return all_responses

    async def survey_stream(
        self,
        input_data: SurveyInput,
        temperature: float = 0.7,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream survey execution with progress updates.

        Yields progress events as each character responds.

        Args:
            input_data: SurveyInput
            temperature: LLM temperature

        Yields:
            Progress events with response data
        """
        if not input_data.characters or not input_data.questions:
            yield {
                "event": "error",
                "data": "No characters or questions provided",
            }
            return

        total_tasks = len(input_data.characters) * len(input_data.questions)
        completed = 0
        all_responses: list[CharacterSurveyResponse] = []

        for question in input_data.questions:
            question_responses: list[tuple[str, str]] = []

            for character in input_data.characters:
                # Get prior responses if chaining (only in sequential mode)
                prior = None
                if input_data.mode == SurveyMode.SEQUENTIAL and input_data.chain_prompts:
                    prior = question_responses

                try:
                    response = await self._ask_single_character(
                        character=character,
                        question=question,
                        year=input_data.year,
                        location=input_data.location,
                        era=input_data.era,
                        prior_responses=prior,
                        temperature=temperature,
                    )

                    all_responses.append(response)
                    question_responses.append((character.name, response.response))

                    completed += 1
                    progress = int((completed / total_tasks) * 100)

                    yield {
                        "event": "response",
                        "data": {
                            "character_name": response.character_name,
                            "question": response.question,
                            "response": response.response,
                            "sentiment": response.sentiment,
                            "emotional_tone": response.emotional_tone,
                        },
                        "character_name": response.character_name,
                        "question": question,
                        "progress": progress,
                    }

                except Exception as e:
                    completed += 1
                    logger.warning(f"Failed to get response from {character.name}: {e}")
                    yield {
                        "event": "error",
                        "data": f"Failed for {character.name}: {str(e)}",
                        "character_name": character.name,
                        "question": question,
                        "progress": int((completed / total_tasks) * 100),
                    }

        # Generate and yield summary if requested
        if input_data.include_summary and all_responses:
            summaries = []
            for question in input_data.questions:
                q_responses = [
                    (r.character_name, r.response)
                    for r in all_responses
                    if r.question == question
                ]
                if q_responses:
                    try:
                        q_summary = await self._generate_summary(question, q_responses)
                        summaries.append(f"Q: {question}\n{q_summary}")
                    except Exception as e:
                        logger.warning(f"Failed to generate summary: {e}")

            if summaries:
                yield {
                    "event": "summary",
                    "data": "\n\n".join(summaries),
                    "progress": 100,
                }

        # Done event
        yield {
            "event": "done",
            "data": {
                "total_responses": len(all_responses),
                "characters_surveyed": len(input_data.characters),
                "questions_asked": len(input_data.questions),
            },
            "progress": 100,
        }
