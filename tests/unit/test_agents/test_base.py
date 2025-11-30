"""Tests for base agent classes.

Tests:
    - BaseAgent initialization
    - AgentResult dataclass
    - AgentChain execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.agents.base import AgentResult, BaseAgent, AgentChain
from app.config import ProviderType
from app.core.providers import LLMResponse, ModelCapability
from pydantic import BaseModel


# Test models
class MockOutput(BaseModel):
    """Mock output model for testing."""
    value: str
    count: int = 0


class MockAgent(BaseAgent[str, MockOutput]):
    """Concrete agent for testing."""

    response_model = MockOutput

    def get_system_prompt(self) -> str:
        return "Test system prompt"

    def get_prompt(self, input_data: str) -> str:
        return f"Test prompt for: {input_data}"

    async def run(self, input_data: str) -> AgentResult[MockOutput]:
        return await self._call_llm(input_data)


@pytest.mark.fast
class TestAgentResult:
    """Tests for AgentResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = AgentResult(
            success=True,
            content=MockOutput(value="test"),
            latency_ms=100,
            model_used="test-model",
        )
        assert result.success is True
        assert result.failed is False
        assert result.content.value == "test"
        assert result.latency_ms == 100

    def test_failed_result(self):
        """Test creating a failed result."""
        result = AgentResult(
            success=False,
            error="Test error",
            latency_ms=50,
        )
        assert result.success is False
        assert result.failed is True
        assert result.error == "Test error"
        assert result.content is None

    def test_result_metadata(self):
        """Test result metadata."""
        result = AgentResult(
            success=True,
            content=MockOutput(value="test"),
            metadata={"key": "value"},
        )
        assert result.metadata["key"] == "value"


@pytest.mark.fast
class TestBaseAgent:
    """Tests for BaseAgent."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = MockAgent()
        assert agent.name == "MockAgent"
        assert agent.router is not None

    def test_agent_initialization_with_router(self):
        """Test agent initialization with custom router."""
        mock_router = MagicMock()
        agent = MockAgent(router=mock_router)
        assert agent.router is mock_router

    def test_agent_initialization_with_name(self):
        """Test agent initialization with custom name."""
        agent = MockAgent(name="CustomName")
        assert agent.name == "CustomName"

    def test_get_system_prompt(self):
        """Test getting system prompt."""
        agent = MockAgent()
        prompt = agent.get_system_prompt()
        assert prompt == "Test system prompt"

    def test_get_prompt(self):
        """Test getting user prompt."""
        agent = MockAgent()
        prompt = agent.get_prompt("test input")
        assert "test input" in prompt

    @pytest.mark.asyncio
    async def test_call_llm_success(self):
        """Test successful LLM call."""
        mock_router = MagicMock()
        mock_response = LLMResponse(
            content=MockOutput(value="test", count=5),
            model="test-model",
            provider=ProviderType.GOOGLE,
        )
        mock_router.call_structured = AsyncMock(return_value=mock_response)

        agent = MockAgent(router=mock_router)
        result = await agent.run("test input")

        assert result.success is True
        assert result.content.value == "test"
        assert result.content.count == 5
        assert result.model_used == "test-model"

    @pytest.mark.asyncio
    async def test_call_llm_failure(self):
        """Test failed LLM call."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(side_effect=Exception("API error"))

        agent = MockAgent(router=mock_router)
        result = await agent.run("test input")

        assert result.success is False
        assert "API error" in result.error


@pytest.mark.fast
class TestAgentChain:
    """Tests for AgentChain."""

    @pytest.mark.asyncio
    async def test_chain_execution(self):
        """Test chain executes agents in order."""
        # Create mock agents
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(
            return_value=LLMResponse(
                content=MockOutput(value="result"),
                model="test-model",
                provider=ProviderType.GOOGLE,
            )
        )

        agent1 = MockAgent(router=mock_router, name="Agent1")
        agent2 = MockAgent(router=mock_router, name="Agent2")

        chain = AgentChain([agent1, agent2])
        results = await chain.run("initial input")

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is True

    @pytest.mark.asyncio
    async def test_chain_stops_on_failure(self):
        """Test chain stops when agent fails."""
        mock_router = MagicMock()
        mock_router.call_structured = AsyncMock(side_effect=Exception("Error"))

        agent1 = MockAgent(router=mock_router, name="Agent1")
        agent2 = MockAgent(router=mock_router, name="Agent2")

        chain = AgentChain([agent1, agent2])
        results = await chain.run("input")

        assert len(results) == 1
        assert results[0].success is False
