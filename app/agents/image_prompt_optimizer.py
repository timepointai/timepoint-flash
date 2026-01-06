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
        max_words: Target maximum word count (default: 120)
    """

    full_prompt: str
    year: int
    query: str
    style: str = "photorealistic"
    max_words: int = 120


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

Your job is to take verbose, overloaded image prompts and compress them to 50-150 words
while preserving the essential visual elements that will produce high-quality images.

## Key Principles

1. **Focus on visuals, not narrative**: Remove backstory, emotions, and implied actions
2. **Limit characters**: Keep only 1-3 focal characters; describe their appearance briefly
3. **Single focal point**: Choose ONE clear visual focus
4. **Era accuracy**: Flag and remove any anachronistic elements
5. **Concrete details**: Keep specific visual details (colors, materials, lighting)
6. **Style cues**: Preserve and enhance style directives (photorealistic, 8k, etc.)

## What to REMOVE:
- Character motivations and emotions
- Historical context and significance
- Multiple competing focal points
- Redundant descriptions
- Background character details
- Narrative tension descriptions

## What to PRESERVE:
- Setting and location
- Time period visual cues
- Lighting and atmosphere
- 1-2 primary character descriptions (appearance only)
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
Produce a compressed prompt that an image model can render effectively.
The optimized prompt should read as a direct instruction to an image generator."""


def get_optimizer_prompt(
    full_prompt: str,
    year: int,
    query: str,
    style: str,
    max_words: int,
) -> str:
    """Build the optimizer prompt."""
    return f"""Optimize this image prompt for the year {year}.

ORIGINAL QUERY: {query}

FULL PROMPT ({len(full_prompt.split())} words):
{full_prompt}

TARGET: Compress to {max_words} words maximum while preserving visual quality.
STYLE: {style}
YEAR: {year} (check for anachronisms)

Analyze the prompt for issues, then produce an optimized version.
Focus on what the image should SHOW, not what it should MEAN."""


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
