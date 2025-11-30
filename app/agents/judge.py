"""Judge Agent for query validation.

The Judge Agent validates temporal queries and classifies their type
to determine if they can be processed into visual scenes.

Examples:
    >>> from app.agents.judge import JudgeAgent
    >>> agent = JudgeAgent()
    >>> result = await agent.run("signing of the declaration")
    >>> if result.success:
    ...     print(result.content.is_valid)  # True
    ...     print(result.content.query_type)  # QueryType.HISTORICAL

    >>> # Invalid query
    >>> result = await agent.run("what is the meaning of life")
    >>> print(result.content.is_valid)  # False

Tests:
    - tests/unit/test_agents/test_judge.py::test_judge_valid_historical
    - tests/unit/test_agents/test_judge.py::test_judge_valid_fictional
    - tests/unit/test_agents/test_judge.py::test_judge_invalid_abstract
    - tests/unit/test_agents/test_judge.py::test_judge_extracts_metadata
"""

from __future__ import annotations

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import judge as judge_prompts
from app.schemas import JudgeResult, QueryType


class JudgeAgent(BaseAgent[str, JudgeResult]):
    """Agent that validates and classifies temporal queries.

    The Judge determines if a query can be transformed into a
    visual scene and extracts relevant metadata.

    Attributes:
        response_model: JudgeResult Pydantic model
        name: "JudgeAgent"

    Valid Query Types:
        - historical: Real historical events/moments
        - fictional: Scenes from fiction/literature
        - speculative: "What if" scenarios
        - contemporary: Modern/recent events

    Invalid Query Types:
        - Abstract concepts without temporal context
        - Technical/educational questions
        - Personal/unvisualizable queries

    Examples:
        >>> agent = JudgeAgent()

        >>> # Historical event
        >>> result = await agent.run("battle of thermopylae")
        >>> result.content.is_valid  # True
        >>> result.content.query_type  # QueryType.HISTORICAL

        >>> # Fictional scene
        >>> result = await agent.run("the red wedding from game of thrones")
        >>> result.content.query_type  # QueryType.FICTIONAL

        >>> # Invalid query
        >>> result = await agent.run("what is love")
        >>> result.content.is_valid  # False
        >>> result.content.reason  # "Abstract concept without temporal context"

    Tests:
        - tests/unit/test_agents/test_judge.py::test_judge_initialization
        - tests/unit/test_agents/test_judge.py::test_judge_run_valid
        - tests/unit/test_agents/test_judge.py::test_judge_run_invalid
    """

    response_model = JudgeResult

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Judge Agent.

        Args:
            router: LLM router (creates one if not provided)
        """
        super().__init__(router=router, name="JudgeAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for query validation.

        Returns:
            System prompt defining validation rules
        """
        return judge_prompts.get_system_prompt()

    def get_prompt(self, query: str) -> str:
        """Get the user prompt for validating a query.

        Args:
            query: The user's temporal query

        Returns:
            Formatted validation prompt
        """
        return judge_prompts.get_prompt(query)

    async def run(self, query: str) -> AgentResult[JudgeResult]:
        """Validate and classify a temporal query.

        Args:
            query: The user's temporal query (e.g., "rome 50 BCE")

        Returns:
            AgentResult containing JudgeResult with:
                - is_valid: Whether query can be processed
                - query_type: Classification (historical, fictional, etc.)
                - cleaned_query: Improved version of the query
                - detected_year: Year extracted from query
                - detected_location: Location extracted from query
                - detected_figures: Historical figures mentioned

        Examples:
            >>> result = await agent.run("signing of the declaration")
            >>> if result.success and result.content.is_valid:
            ...     print(f"Cleaned: {result.content.cleaned_query}")
            ...     print(f"Year: {result.content.detected_year}")
        """
        result = await self._call_llm(query, temperature=0.3)

        # Add metadata about the validation
        if result.success and result.content:
            result.metadata["is_valid"] = result.content.is_valid
            result.metadata["query_type"] = result.content.query_type.value

        return result

    @staticmethod
    def create_failed_result(reason: str) -> JudgeResult:
        """Create a JudgeResult for a failed validation.

        Useful when the agent itself fails (e.g., API error)
        and you need a default invalid result.

        Args:
            reason: The failure reason

        Returns:
            JudgeResult with is_valid=False

        Examples:
            >>> result = JudgeAgent.create_failed_result("API timeout")
            >>> result.is_valid  # False
            >>> result.reason  # "API timeout"
        """
        return JudgeResult(
            is_valid=False,
            query_type=QueryType.INVALID,
            reason=reason,
        )
