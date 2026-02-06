"""Critique Agent for post-generation quality review.

A generic agent that reviews any pipeline step's output for:
- Anachronisms (cultural, linguistic, material)
- Voice distinctiveness (dialog)
- Timeline accuracy
- Cultural accuracy (deity names, idioms, social conventions)

The CritiqueAgent wraps any agent output and returns actionable issues.
When critical issues are found, the original agent can be re-run with
the critique injected as additional context (one retry max).

Examples:
    >>> from app.agents.critique import CritiqueAgent, CritiqueInput
    >>> agent = CritiqueAgent(router)
    >>> result = await agent.run(CritiqueInput(
    ...     step_name="dialog",
    ...     output_json='{"lines": [...]}',
    ...     year=79,
    ...     era="Roman Empire",
    ...     location="Pompeii",
    ...     query="eruption of Vesuvius"
    ... ))
    >>> for issue in result.content.issues:
    ...     print(f"[{issue.severity}] {issue.description}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter

logger = logging.getLogger(__name__)


@dataclass
class CritiqueInput:
    """Input for the Critique Agent.

    Attributes:
        step_name: Which pipeline step produced this output (e.g., "dialog", "characters")
        output_json: The JSON output to critique (serialized string)
        year: Historical year for context
        era: Historical era
        location: Scene location
        query: Original user query
        additional_context: Any extra context (grounding data, scene description, etc.)
    """

    step_name: str
    output_json: str
    year: int
    era: str = ""
    location: str = ""
    query: str = ""
    additional_context: str = ""


class CritiqueIssue(BaseModel):
    """A single issue found during critique."""

    category: str = Field(
        description="Category: 'anachronism', 'cultural_error', 'voice', 'timeline', 'idiom', 'naming'"
    )
    severity: str = Field(
        description="'critical' (must fix), 'warning' (should fix), 'minor' (note)"
    )
    description: str = Field(
        description="What's wrong and why"
    )
    fix_suggestion: str = Field(
        description="Specific correction to apply"
    )
    location: str = Field(
        description="Where in the output the issue occurs (e.g., character name, dialog line)"
    )


class CritiqueOutput(BaseModel):
    """Output from the Critique Agent."""

    issues: list[CritiqueIssue] = Field(
        default_factory=list,
        description="Issues found in the output"
    )
    has_critical: bool = Field(
        description="Whether any critical issues were found (triggers retry)"
    )
    overall_assessment: str = Field(
        description="Brief summary of quality"
    )
    revision_instructions: str = Field(
        default="",
        description="If has_critical=true, specific instructions for the re-run"
    )


SYSTEM_PROMPT = """You are a historical accuracy and quality reviewer for TIMEPOINT,
an AI system that generates immersive visual scenes from temporal moments.

Your job is to find CONCRETE errors in generated content. You are NOT a general
quality scorer — you find specific, fixable problems.

## What You Check

### Anachronisms
- Objects, technology, or materials that didn't exist in this time/place
- Clothing or fashion from the wrong era
- Architecture inconsistent with the period

### Cultural Errors
- Wrong deity pantheon (Greek gods in Roman setting, or vice versa)
- Modern English idioms in historical dialog ("six feet under", "beat around the bush",
  "back to the drawing board", "raining cats and dogs", etc.)
- Social conventions from wrong era (e.g., handshakes in ancient Rome)
- Literary character names used as if they were real people (e.g., "Fortunata" from
  Petronius's Satyricon used as a generic Roman woman's name)

### Voice Distinctiveness (dialog only)
- Two or more characters who sound identical (same sentence structure, vocabulary level)
- A slave speaking like a senator, or vice versa, without justification
- Silent characters listed as speaking, or speaking characters with no lines
- Generic disaster-movie dialog that any character could say

### Timeline Accuracy
- Events compressed or expanded beyond historical record
- Reactions to events that haven't happened yet in the timeline
- Conflation of events from different dates (e.g., Vesuvius erupted Aug 24, 79 AD;
  pyroclastic surges came the morning of Aug 25)

## Rules
1. Only flag CONCRETE, specific issues — not vague quality concerns
2. Each issue must have a specific fix_suggestion
3. "critical" = factually wrong or breaks immersion; "warning" = inaccurate but minor;
   "minor" = could be better but not wrong
4. If there are no issues, return an empty issues list with has_critical=false
5. Be precise about location (which character, which line, which field)
6. Maximum 5 issues — focus on the most impactful ones"""


def get_critique_prompt(
    step_name: str,
    output_json: str,
    year: int,
    era: str,
    location: str,
    query: str,
    additional_context: str = "",
) -> str:
    """Build the critique prompt."""
    context_section = ""
    if additional_context:
        context_section = f"\n\nADDITIONAL CONTEXT:\n{additional_context}"

    return f"""Review this {step_name} output for errors.

SCENE: "{query}"
YEAR: {year}
ERA: {era or 'Unknown'}
LOCATION: {location}

{step_name.upper()} OUTPUT TO REVIEW:
{output_json}
{context_section}

Find CONCRETE errors: anachronisms, cultural mistakes, voice problems,
timeline inaccuracies, modern idioms. Be specific — cite the exact text that's wrong
and what it should be instead.

If the output is acceptable, return has_critical=false with an empty issues list."""


class CritiqueAgent(BaseAgent[CritiqueInput, CritiqueOutput]):
    """Agent that reviews pipeline outputs for historical and quality issues.

    Used as an optional post-processing step on Dialog and Character outputs.
    When critical issues are found, the original agent re-runs with the
    critique's revision_instructions injected as additional context.

    One critique + one retry maximum — if the retry still has issues,
    accept it and move on.
    """

    response_model = CritiqueOutput

    def __init__(self, router: LLMRouter | None = None) -> None:
        """Initialize the Critique Agent."""
        super().__init__(router=router, name="CritiqueAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt."""
        return SYSTEM_PROMPT

    def get_prompt(self, input_data: CritiqueInput) -> str:
        """Get the user prompt."""
        return get_critique_prompt(
            step_name=input_data.step_name,
            output_json=input_data.output_json,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            query=input_data.query,
            additional_context=input_data.additional_context,
        )

    async def run(
        self, input_data: CritiqueInput
    ) -> AgentResult[CritiqueOutput]:
        """Run the critique.

        Args:
            input_data: CritiqueInput with the output to review

        Returns:
            AgentResult containing CritiqueOutput with issues found
        """
        result = await self._call_llm(input_data, temperature=0.3)

        if result.success and result.content:
            critical_count = sum(
                1 for i in result.content.issues if i.severity == "critical"
            )
            result.metadata["issues_count"] = len(result.content.issues)
            result.metadata["critical_count"] = critical_count

            if critical_count > 0:
                logger.warning(
                    f"Critique found {critical_count} critical issues in {input_data.step_name}: "
                    f"{[i.description for i in result.content.issues if i.severity == 'critical']}"
                )
            else:
                logger.info(
                    f"Critique of {input_data.step_name}: {len(result.content.issues)} issues "
                    f"(0 critical)"
                )

        return result
