"""Image Prompt Optimizer Agent for prompt compression and quality control.

This agent takes the full image prompt (often 300-400+ words) and compresses
it to an optimal length for image generation (50-150 words) while preserving
the most important visual elements.

It also validates for:
- Anachronisms (modern elements in historical scenes)
- Prompt overload (too many competing focal points)
- Hallucinations (impossible or contradictory elements)

Examples:
    >>> from app.agents.image_prompt_optimizer import ImagePromptOptimizerAgent
    >>> agent = ImagePromptOptimizerAgent(router)
    >>> result = await agent.run(ImagePromptOptimizerInput(
    ...     full_prompt="A photorealistic historical scene...",
    ...     year=1997,
    ...     query="Deep Blue defeats Kasparov"
    ... ))
    >>> print(result.content.optimized_prompt)  # Compressed version

Tests:
    - tests/unit/test_agents/test_image_prompt_optimizer.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter

logger = logging.getLogger(__name__)


@dataclass
class ImagePromptOptimizerInput:
    """Input for the Image Prompt Optimizer Agent.

    Attributes:
        full_prompt: The full image prompt (may be 300+ words)
        year: The historical year for anachronism detection
        query: Original user query for context
        style: Image style hint (photorealistic, artistic, etc.)
        max_words: Target maximum word count (default: 77)
        tension_arc: Narrative tension level (rising/falling/climactic/resolved)
        emotional_beats: Key emotions to physicalize in the image
    """

    full_prompt: str
    year: int
    query: str
    style: str = "photorealistic"
    max_words: int = 77
    tension_arc: str = ""
    emotional_beats: list[str] | None = None


class PromptIssue(BaseModel):
    """An issue detected in the prompt."""

    issue_type: str = Field(
        description="Type: 'anachronism', 'overload', 'hallucination', 'contradiction'"
    )
    description: str = Field(
        description="Brief description of the issue"
    )
    severity: str = Field(
        description="'critical' (must fix), 'warning' (should fix), 'minor' (optional)"
    )
    fix_applied: str = Field(
        description="How this was addressed in the optimized prompt"
    )


class ImagePromptOptimizerOutput(BaseModel):
    """Output from the Image Prompt Optimizer Agent.

    Contains the compressed prompt and quality analysis.
    """

    optimized_prompt: str = Field(
        description="Compressed prompt optimized for image generation (50-150 words)"
    )

    word_count: int = Field(
        description="Word count of the optimized prompt"
    )

    focal_elements: list[str] = Field(
        default_factory=list,
        description="The 3-5 key visual elements preserved in the prompt"
    )

    removed_elements: list[str] = Field(
        default_factory=list,
        description="Elements removed to reduce complexity"
    )

    issues_found: list[PromptIssue] = Field(
        default_factory=list,
        description="Quality issues detected and addressed"
    )

    quality_score: int = Field(
        ge=1, le=10,
        description="Overall prompt quality score (1-10)"
    )

    optimization_notes: str = Field(
        description="Brief explanation of optimization decisions"
    )


SYSTEM_PROMPT = """You are an expert image prompt optimizer for historical scene generation.

Your job is to take verbose, overloaded image prompts and compress them to 50-80 words
while preserving the essential visual elements that will produce high-quality images.

## Key Principles

1. **TRANSLATE emotion into physicality**: Do NOT remove emotional content — convert it
   into visible body language, facial expressions, and environmental cues.
   "Terror" → "wide eyes, open mouth, body recoiling, dropped objects"
   "Climactic tension" → "frozen mid-action, white knuckles, sweat on brow"
   "Grief" → "collapsed posture, hands covering face, slack jaw"
2. **Limit characters**: Keep only 1-3 focal characters; describe their appearance briefly
3. **Single focal point**: Choose ONE clear visual focus
4. **Era accuracy**: Flag and remove any anachronistic elements
5. **Concrete details**: Keep specific visual details (colors, materials, lighting)
6. **Style cues**: Preserve and enhance style directives (photorealistic, 8k, etc.)
7. **Front-load importance**: Put composition, lighting, and era cues in the FIRST 40 words;
   character details and style in the remaining words

## What to REMOVE:
- Abstract narrative (backstory, historical significance, "this moment matters because...")
- Multiple competing focal points
- Redundant descriptions
- Background character details
- Relationship descriptions

## What to TRANSLATE (not remove):
- Tension arc → physical body language and environmental urgency
- Emotional beats → facial expressions, posture, gesture, dropped/gripped objects
- Stakes → environmental danger cues (smoke, fire, approaching threat visible)

## What to PRESERVE:
- Setting and location
- Time period visual cues
- Lighting and atmosphere
- 1-2 primary character descriptions (appearance + physicalized emotion)
- Camera angle/composition
- Color palette
- Style directives

## Anachronism Detection
For the given year, flag:
- Technology that didn't exist yet
- Clothing/fashion from wrong era
- Architecture inconsistent with period
- Objects or materials not available

## Output Format
Produce a compressed prompt (~77 words / ~100 tokens) that an image model can render.
The optimized prompt should read as a direct instruction to an image generator.
The image should feel like a CAUGHT MOMENT, not a posed tableau."""


def get_optimizer_prompt(
    full_prompt: str,
    year: int,
    query: str,
    style: str,
    max_words: int,
    tension_arc: str = "",
    emotional_beats: list[str] | None = None,
) -> str:
    """Build the optimizer prompt."""
    emotion_section = ""
    if tension_arc or emotional_beats:
        emotion_section = f"""
EMOTIONAL CONTEXT (translate into VISIBLE body language, do NOT discard):
- Tension arc: {tension_arc or 'not specified'}
- Emotional beats: {', '.join(emotional_beats) if emotional_beats else 'not specified'}
Convert these into physical cues: facial expressions, posture, gestures, environmental urgency.
The image must FEEL the emotion, not just depict a static scene."""

    return f"""Optimize this image prompt for the year {year}.

ORIGINAL QUERY: {query}

FULL PROMPT ({len(full_prompt.split())} words):
{full_prompt}
{emotion_section}

TARGET: Compress to {max_words} words maximum (~100 tokens).
STYLE: {style}
YEAR: {year} (check for anachronisms)
FRONT-LOAD: Put composition + lighting + era cues in the first 40 words.

Analyze the prompt for issues, then produce an optimized version.
The image should look like a CAUGHT MOMENT — not a posed tableau.
Translate narrative emotion into visible physicality."""


class ImagePromptOptimizerAgent(BaseAgent[ImagePromptOptimizerInput, ImagePromptOptimizerOutput]):
    """Agent that optimizes image prompts for better generation quality.

    Takes verbose prompts (300+ words) and compresses them to optimal
    length (50-150 words) while:
    - Preserving key visual elements
    - Removing narrative/emotional content
    - Detecting and fixing anachronisms
    - Ensuring single clear focal point

    Attributes:
        response_model: ImagePromptOptimizerOutput
        name: "ImagePromptOptimizerAgent"

    Examples:
        >>> agent = ImagePromptOptimizerAgent(router)
        >>> result = await agent.run(input_data)
        >>> optimized = result.content.optimized_prompt
    """

    response_model = ImagePromptOptimizerOutput

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize the optimizer agent."""
        super().__init__(router=router, name="ImagePromptOptimizerAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return SYSTEM_PROMPT

    def get_prompt(self, input_data: ImagePromptOptimizerInput) -> str:
        """Get the user prompt."""
        return get_optimizer_prompt(
            full_prompt=input_data.full_prompt,
            year=input_data.year,
            query=input_data.query,
            style=input_data.style,
            max_words=input_data.max_words,
            tension_arc=input_data.tension_arc,
            emotional_beats=input_data.emotional_beats,
        )

    async def run(
        self, input_data: ImagePromptOptimizerInput
    ) -> AgentResult[ImagePromptOptimizerOutput]:
        """Optimize the image prompt.

        Args:
            input_data: The full prompt and metadata

        Returns:
            AgentResult containing optimized prompt and analysis
        """
        original_words = len(input_data.full_prompt.split())

        logger.info(
            f"Optimizing prompt: {original_words} words -> target {input_data.max_words}"
        )

        result = await self._call_llm(input_data, temperature=0.4)

        if result.success and result.content:
            compression_ratio = original_words / max(result.content.word_count, 1)

            result.metadata["original_words"] = original_words
            result.metadata["optimized_words"] = result.content.word_count
            result.metadata["compression_ratio"] = round(compression_ratio, 2)
            result.metadata["issues_count"] = len(result.content.issues_found)
            result.metadata["quality_score"] = result.content.quality_score

            # Log significant issues
            critical_issues = [
                i for i in result.content.issues_found
                if i.severity == "critical"
            ]
            if critical_issues:
                logger.warning(
                    f"Critical prompt issues found: {[i.description for i in critical_issues]}"
                )

            logger.info(
                f"Prompt optimized: {original_words} -> {result.content.word_count} words "
                f"({compression_ratio:.1f}x compression), quality={result.content.quality_score}/10"
            )

        return result
