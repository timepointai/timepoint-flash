"""Character Bio Agent for Phase 2 of parallel character generation.

Generates detailed bio for a single character, run in parallel for all characters.

Examples:
    >>> from app.agents.character_bio import CharacterBioAgent
    >>> agent = CharacterBioAgent()
    >>> result = await agent.run(CharacterBioInput(...))
    >>> print(result.content.name, result.content.description)

Tests:
    - tests/unit/test_character_bio.py
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import AgentResult, BaseAgent
from app.core.llm_router import LLMRouter
from app.prompts import character_bio as char_bio_prompts
from app.schemas import Character
from app.schemas.character_identification import CharacterIdentification, CharacterStub
from app.schemas.graph import GraphData


@dataclass
class CharacterBioInput:
    """Input data for Character Bio Agent.

    Attributes:
        stub: The CharacterStub to generate bio for
        full_cast: Full CharacterIdentification with all characters
        query: The cleaned query text
        year: Year of the scene
        era: Historical era
        location: Geographic location
        setting: Scene setting description
        atmosphere: Scene atmosphere
        tension_level: Dramatic tension
        graph_data: Optional relationship graph for this character
    """

    stub: CharacterStub
    full_cast: CharacterIdentification
    query: str
    year: int
    era: str | None = None
    location: str = ""
    setting: str = ""
    atmosphere: str = ""
    tension_level: str = "medium"
    graph_data: "GraphData | None" = None  # Relationships for this character

    @classmethod
    def from_identification(
        cls,
        stub: CharacterStub,
        full_cast: CharacterIdentification,
        query: str,
        year: int,
        era: str | None,
        location: str,
        setting: str,
        atmosphere: str,
        tension_level: str,
        graph_data: "GraphData | None" = None,
    ) -> "CharacterBioInput":
        """Create input for a specific character bio.

        Args:
            stub: CharacterStub to generate bio for
            full_cast: Full CharacterIdentification for context
            query: Original query
            year: Scene year
            era: Historical era
            location: Location
            setting: Scene setting
            atmosphere: Scene atmosphere
            tension_level: Tension level
            graph_data: Optional relationship graph for context

        Returns:
            CharacterBioInput for this character
        """
        return cls(
            stub=stub,
            full_cast=full_cast,
            query=query,
            year=year,
            era=era,
            location=location,
            setting=setting,
            atmosphere=atmosphere,
            tension_level=tension_level,
            graph_data=graph_data,
        )


class CharacterBioAgent(BaseAgent[CharacterBioInput, Character]):
    """Agent that generates a detailed bio for one character (Phase 2).

    Receives full cast context to ensure relationship coherence.
    Multiple instances run in parallel for all characters.

    Attributes:
        response_model: Character Pydantic model
        name: "CharacterBioAgent"

    Examples:
        >>> agent = CharacterBioAgent()
        >>> result = await agent.run(CharacterBioInput(
        ...     stub=caesar_stub,
        ...     full_cast=char_identification,
        ...     query="assassination of Julius Caesar",
        ...     year=-44,
        ...     ...
        ... ))
        >>> result.content.name  # "Julius Caesar"

    Tests:
        - tests/unit/test_character_bio.py::test_bio_agent
    """

    response_model = Character

    def __init__(
        self,
        router: LLMRouter | None = None,
    ) -> None:
        """Initialize Character Bio Agent."""
        super().__init__(router=router, name="CharacterBioAgent")

    def get_system_prompt(self) -> str:
        """Get the system prompt for character bio generation."""
        return char_bio_prompts.get_system_prompt()

    def get_prompt(self, input_data: CharacterBioInput) -> str:
        """Get the user prompt for character bio generation."""
        stub = input_data.stub
        cast_context = input_data.full_cast.get_cast_context()

        # Extract relationship context from graph data
        relationship_context = ""
        if input_data.graph_data:
            relationships = input_data.graph_data.get_relationships_for(stub.name)
            if relationships:
                rel_lines = []
                for rel in relationships:
                    rel_lines.append(
                        f"- {rel.character_a} <-> {rel.character_b}: "
                        f"{rel.relationship_type} ({rel.emotional_tone})"
                    )
                relationship_context = "\n".join(rel_lines)

        return char_bio_prompts.get_prompt(
            character_name=stub.name,
            character_role=stub.role.value,
            character_brief=stub.brief_description,
            speaks_in_scene=stub.speaks_in_scene,
            key_relationships=stub.key_relationships,
            cast_context=cast_context,
            query=input_data.query,
            year=input_data.year,
            era=input_data.era,
            location=input_data.location,
            setting=input_data.setting,
            atmosphere=input_data.atmosphere,
            tension_level=input_data.tension_level,
            relationship_context=relationship_context,
        )

    async def run(self, input_data: CharacterBioInput) -> AgentResult[Character]:
        """Generate detailed bio for a single character.

        Args:
            input_data: CharacterBioInput with stub and cast context

        Returns:
            AgentResult containing Character
        """
        result = await self._call_llm(input_data, temperature=0.7)

        if result.success and result.content:
            result.metadata["character_name"] = result.content.name
            result.metadata["speaks"] = result.content.speaks_in_scene

        return result


def create_fallback_character(stub: CharacterStub) -> Character:
    """Create a minimal fallback character from a stub.

    Used when bio generation fails for a character.

    Args:
        stub: CharacterStub to convert

    Returns:
        Minimal Character with basic info
    """
    return Character(
        name=stub.name,
        role=stub.role,
        description=stub.brief_description,
        clothing="Period-appropriate attire",
        expression="Appropriate expression for the moment",
        pose="Standing naturally",
        action="Observing the scene",
        speaks_in_scene=stub.speaks_in_scene,
    )
