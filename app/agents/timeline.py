"""Timeline Agent for temporal extraction.

The Timeline Agent extracts precise temporal coordinates from a validated query,
including year, month, day, season, location, and historical era.

Examples:
    >>> from app.agents.timeline import TimelineAgent, TimelineInput
    >>> agent = TimelineAgent()
    >>> input_data = TimelineInput(
    ...     query="signing of the declaration",
    ...     query_type="historical"
    ... )
    >>> result = await agent.run(input_data)
    >>> if result.success:
    ...     print(result.content.year)  # 1776
    ...     print(result.content.location)  # "Independence Hall, Philadelphia"

Tests:
    - tests/unit/test_agents/test_timeline.py::test_timeline_historical
    - tests/unit/test_agents/test_timeline.py::test_timeline_bce
    - tests/unit/test_agents/test_timeline.py::test_timeline_fictional
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import timeline as timeline_prompts
from app.schemas import JudgeResult, TimelineData


@dataclass
class TimelineInput:
    """Input data for Timeline Agent.

    Attributes:
        query: The cleaned query text
        query_type: Type classification (historical, fictional, etc.)
        detected_year: Year hint from Judge (optional)
        detected_location: Location hint from Judge (optional)
    """

    query: str
    query_type: str = "historical"
    detected_year: int | None = None
    detected_location: str | None = None

    @classmethod
    def from_judge_result(cls, query: str, judge: JudgeResult) -> "TimelineInput":
        """Create TimelineInput from JudgeResult.

        Args:
            query: Original query
            judge: JudgeResult from Judge Agent

        Returns:
            TimelineInput populated with Judge data
        """
        return cls(
            query=judge.cleaned_query or query,
            query_type=judge.query_type.value,
            detected_year=judge.detected_year,
            detected_location=judge.detected_location,
        )


class TimelineAgent(BaseAgent[TimelineInput, TimelineData]):
    """Agent that extracts temporal coordinates from queries.

    Determines precise dates, locations, and historical context
    for scene generation.

    Attributes:
        response_model: TimelineData Pydantic model
        name: "TimelineAgent"

    Temporal Fields Extracted:
        - year: Integer (negative for BCE)
        - month: 1-12 (optional)
        - day: 1-31 (optional)
        - hour: 0-23 (optional)
        - season: spring/summer/fall/winter
        - time_of_day: dawn/morning/midday/afternoon/evening/night

    Examples:
        >>> agent = TimelineAgent()

        >>> # Historical event with known date
        >>> input_data = TimelineInput(query="signing of the declaration")
        >>> result = await agent.run(input_data)
        >>> result.content.year  # 1776
        >>> result.content.month  # 7
        >>> result.content.day  # 4

        >>> # BCE date
        >>> input_data = TimelineInput(query="assassination of julius caesar")
        >>> result = await agent.run(input_data)
        >>> result.content.year  # -44
        >>> result.content.display_year  # "44 BCE"

    Tests:
        - tests/unit/test_agents/test_timeline.py::test_timeline_initialization
        - tests/unit/test_agents/test_timeline.py::test_timeline_run
    """

    response_model = TimelineData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Timeline Agent.

        Args:
            router: LLM router (creates one if not provided)
        """
        super().__init__(router=router, name="TimelineAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for temporal extraction.

        Returns:
            System prompt with timeline guidelines
        """
        return timeline_prompts.get_system_prompt()

    def get_prompt(self, input_data: TimelineInput) -> str:
        """Get the user prompt for temporal extraction.

        Args:
            input_data: TimelineInput with query and hints

        Returns:
            Formatted extraction prompt
        """
        return timeline_prompts.get_prompt(
            query=input_data.query,
            query_type=input_data.query_type,
            detected_year=input_data.detected_year,
            detected_location=input_data.detected_location,
        )

    async def run(self, input_data: TimelineInput) -> AgentResult[TimelineData]:
        """Extract temporal coordinates from a query.

        Args:
            input_data: TimelineInput with query and hints

        Returns:
            AgentResult containing TimelineData with:
                - year: Year (negative for BCE)
                - month/day/hour: Specific date if known
                - season: Season name
                - time_of_day: Time description
                - location: Geographic location
                - era: Historical era name
                - historical_context: Brief context

        Examples:
            >>> result = await agent.run(TimelineInput(query="rome 50 BCE"))
            >>> print(f"{result.content.display_year} - {result.content.location}")
            '50 BCE - Roman Forum, Rome'
        """
        result = await self._call_llm(input_data, temperature=0.5)

        # Add metadata
        if result.success and result.content:
            result.metadata["year"] = result.content.year
            result.metadata["location"] = result.content.location
            result.metadata["is_bce"] = result.content.is_bce

        return result
