"""Base agent class for timepoint generation.

Provides Mirascope-style interface for structured LLM calls with
automatic retry, error handling, and observability.

Examples:
    >>> class MyAgent(BaseAgent[MyInput, MyOutput]):
    ...     async def run(self, input_data: MyInput) -> AgentResult[MyOutput]:
    ...         return await self._call_llm(prompt, MyOutput)

Tests:
    - tests/unit/test_agents/test_base.py
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.core.llm_router import LLMRouter
from app.core.providers import ModelCapability

logger = logging.getLogger(__name__)

# Type variables for input/output
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass
class AgentResult(Generic[OutputT]):
    """Result from an agent execution.

    Attributes:
        success: Whether the agent succeeded
        content: The output content (if successful)
        error: Error message (if failed)
        latency_ms: Execution time in milliseconds
        model_used: The LLM model used
        metadata: Additional metadata

    Examples:
        >>> result = AgentResult(success=True, content=my_data, latency_ms=150)
        >>> if result.success:
        ...     print(result.content)
    """

    success: bool
    content: OutputT | None = None
    error: str | None = None
    latency_ms: int = 0
    model_used: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        """Check if the agent failed."""
        return not self.success


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Abstract base class for pipeline agents.

    Provides structured LLM calls using Mirascope-style patterns
    with automatic error handling and observability.

    Attributes:
        router: LLM router for API calls
        name: Agent name for logging
        capability: Model capability needed

    Subclasses must implement:
        - run(input_data) -> AgentResult
        - get_system_prompt() -> str
        - get_prompt(input_data) -> str
        - response_model: type[OutputT]

    Examples:
        >>> class JudgeAgent(BaseAgent[str, JudgeResult]):
        ...     response_model = JudgeResult
        ...
        ...     def get_system_prompt(self) -> str:
        ...         return "You are a query validator..."
        ...
        ...     def get_prompt(self, query: str) -> str:
        ...         return f"Validate: {query}"
        ...
        ...     async def run(self, query: str) -> AgentResult[JudgeResult]:
        ...         return await self._call_llm(query)

    Tests:
        - tests/unit/test_agents/test_base.py::test_agent_initialization
        - tests/unit/test_agents/test_base.py::test_agent_call_llm
    """

    # Subclasses must define the response model
    response_model: type[OutputT]

    # Default capability (can be overridden)
    capability: ModelCapability = ModelCapability.TEXT

    def __init__(
        self,
        router: LLMRouter | None = None,
        name: str | None = None,
    ) -> None:
        """Initialize agent.

        Args:
            router: LLM router (creates one if not provided)
            name: Agent name for logging (defaults to class name)
        """
        self.router = router or LLMRouter()
        self.name = name or self.__class__.__name__

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def get_prompt(self, input_data: InputT) -> str:
        """Get the user prompt for this agent.

        Args:
            input_data: Input data for prompt generation

        Returns:
            User prompt string
        """
        pass

    @abstractmethod
    async def run(self, input_data: InputT) -> AgentResult[OutputT]:
        """Execute the agent.

        Args:
            input_data: Input data for the agent

        Returns:
            AgentResult with output or error
        """
        pass

    async def _call_llm(
        self,
        input_data: InputT,
        **kwargs: Any,
    ) -> AgentResult[OutputT]:
        """Make a structured LLM call.

        Uses the router to call the LLM with structured output
        and handles errors gracefully.

        Args:
            input_data: Input data for prompt generation
            **kwargs: Additional parameters for the LLM call

        Returns:
            AgentResult with parsed output or error

        Examples:
            >>> async def run(self, query: str) -> AgentResult[JudgeResult]:
            ...     return await self._call_llm(query, temperature=0.3)
        """
        start_time = time.perf_counter()

        try:
            prompt = self.get_prompt(input_data)
            system = self.get_system_prompt()

            logger.debug(f"{self.name}: calling LLM")

            response = await self.router.call_structured(
                prompt=prompt,
                response_model=self.response_model,
                capability=self.capability,
                system=system,
                **kwargs,
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            logger.debug(f"{self.name}: completed in {latency}ms")

            return AgentResult(
                success=True,
                content=response.content,
                latency_ms=latency,
                model_used=response.model,
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

    async def _call_raw(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> AgentResult[str]:
        """Make a raw (unstructured) LLM call.

        Args:
            prompt: The prompt text
            **kwargs: Additional parameters

        Returns:
            AgentResult with raw text output
        """
        start_time = time.perf_counter()

        try:
            response = await self.router.call(
                prompt=prompt,
                capability=self.capability,
                **kwargs,
            )

            latency = int((time.perf_counter() - start_time) * 1000)

            return AgentResult(
                success=True,
                content=response.content,  # type: ignore
                latency_ms=latency,
                model_used=response.model,
            )

        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)

            return AgentResult(
                success=False,
                error=str(e),
                latency_ms=latency,
            )


class AgentChain:
    """Chain multiple agents together.

    Executes agents in sequence, passing output from one
    to the next.

    Examples:
        >>> chain = AgentChain([judge, timeline, scene])
        >>> results = await chain.run("signing of the declaration")
    """

    def __init__(self, agents: list[BaseAgent]) -> None:
        """Initialize chain.

        Args:
            agents: List of agents to execute in order
        """
        self.agents = agents

    async def run(self, initial_input: Any) -> list[AgentResult]:
        """Run the agent chain.

        Args:
            initial_input: Input for the first agent

        Returns:
            List of results from each agent
        """
        results: list[AgentResult] = []
        current_input = initial_input

        for agent in self.agents:
            result = await agent.run(current_input)
            results.append(result)

            if result.failed:
                logger.warning(f"Chain stopped at {agent.name}: {result.error}")
                break

            # Use output as next input
            current_input = result.content

        return results
