"""Graph Agent for character relationships.

The Graph Agent maps relationships, alliances, and tensions
between characters in the scene.

Examples:
    >>> from app.agents.graph import GraphAgent, GraphInput
    >>> agent = GraphAgent()
    >>> result = await agent.run(GraphInput(...))
    >>> for rel in result.content.relationships:
    ...     print(f"{rel.from_character} -> {rel.to_character}: {rel.relationship_type}")

Tests:
    - tests/unit/test_agents/test_graph.py::test_graph_relationships
    - tests/unit/test_agents/test_graph.py::test_graph_factions
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import graph as graph_prompts
from app.schemas.graph import GraphData


@dataclass
class GraphInput:
    """Input data for Graph Agent.

    Attributes:
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        characters: Character data (dicts with name, role, description)
    """

    query: str
    year: int
    era: str | None = None
    location: str = ""
    characters: list[dict] = field(default_factory=list)


class GraphAgent(BaseAgent[GraphInput, GraphData]):
    """Agent that maps character relationships.

    Creates a relationship graph showing alliances,
    rivalries, and power dynamics.

    Attributes:
        response_model: GraphData Pydantic model
        name: "GraphAgent"

    Relationship Types:
        - ally, rival, enemy
        - subordinate, leader
        - mentor, friend, family
        - stranger, neutral

    Examples:
        >>> agent = GraphAgent()
        >>> result = await agent.run(GraphInput(
        ...     query="signing of the declaration",
        ...     year=1776,
        ...     characters=[
        ...         {"name": "John Adams", "role": "primary"},
        ...         {"name": "Thomas Jefferson", "role": "primary"}
        ...     ]
        ... ))
        >>> len(result.content.relationships)
        1

    Tests:
        - tests/unit/test_agents/test_graph.py::test_graph_initialization
        - tests/unit/test_agents/test_graph.py::test_graph_run
    """

    response_model = GraphData

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Graph Agent."""
        super().__init__(router=router, name="GraphAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for relationship mapping."""
        return graph_prompts.get_system_prompt()

    def get_prompt(self, input_data: GraphInput) -> str:
        """Get the user prompt for relationship mapping."""
        return graph_prompts.get_prompt(
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            characters=input_data.characters,
        )

    async def run(self, input_data: GraphInput) -> AgentResult[GraphData]:
        """Map character relationships.

        Args:
            input_data: GraphInput with characters

        Returns:
            AgentResult containing GraphData
        """
        result = await self._call_llm(input_data, temperature=0.5)

        if result.success and result.content:
            result.metadata["relationship_count"] = len(result.content.relationships)
            result.metadata["faction_count"] = len(result.content.factions)

        return result
