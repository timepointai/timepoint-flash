"""Graph step schema for character relationships.

The Graph step maps relationships, alliances, and tensions
between characters in the scene.

Examples:
    >>> from app.schemas.graph import GraphData, Relationship
    >>> rel = Relationship(
    ...     from_character="John Adams",
    ...     to_character="Thomas Jefferson",
    ...     relationship_type="ally",
    ...     tension_level="low"
    ... )

Tests:
    - tests/unit/test_schemas.py::test_graph_data_valid
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    """A relationship between two characters.

    Attributes:
        from_character: Source character name
        to_character: Target character name
        relationship_type: Type of relationship
        tension_level: Tension between them
        description: Brief description
    """

    from_character: str = Field(..., description="Source character")
    to_character: str = Field(..., description="Target character")
    relationship_type: str = Field(
        default="neutral",
        description="Type: ally, rival, subordinate, leader, family, stranger, etc.",
    )
    tension_level: str = Field(
        default="neutral",
        description="Tension: friendly, neutral, tense, hostile",
    )
    description: str | None = Field(
        default=None,
        description="Brief description of the relationship",
    )

    def to_edge(self) -> tuple[str, str, str]:
        """Convert to graph edge tuple."""
        return (self.from_character, self.to_character, self.relationship_type)


class Faction(BaseModel):
    """A group of aligned characters.

    Attributes:
        name: Faction name
        members: Character names in faction
        goal: What this faction wants
    """

    name: str = Field(..., description="Faction name")
    members: list[str] = Field(default_factory=list, description="Member names")
    goal: str | None = Field(default=None, description="Faction goal")


class GraphData(BaseModel):
    """Relationship graph for scene characters.

    Maps how characters relate to each other,
    their alliances, rivalries, and power dynamics.

    Attributes:
        relationships: Pairwise relationships
        factions: Groups of aligned characters
        power_dynamics: Description of power structure
        central_conflict: The main interpersonal conflict
        alliances: Key alliances
        rivalries: Key rivalries
    """

    # Relationships
    relationships: list[Relationship] = Field(
        default_factory=list,
        description="Pairwise character relationships",
    )

    # Groups
    factions: list[Faction] = Field(
        default_factory=list,
        description="Groups of aligned characters",
    )

    # Dynamics
    power_dynamics: str | None = Field(
        default=None,
        description="Power structure description",
    )
    central_conflict: str | None = Field(
        default=None,
        description="Main interpersonal conflict in scene",
    )

    # Key relationships
    alliances: list[str] = Field(
        default_factory=list,
        description="Key alliance descriptions",
    )
    rivalries: list[str] = Field(
        default_factory=list,
        description="Key rivalry descriptions",
    )

    # Context
    historical_context: str | None = Field(
        default=None,
        description="Historical context for relationships",
    )

    def get_relationships_for(self, character: str) -> list[Relationship]:
        """Get all relationships involving a character."""
        return [
            r
            for r in self.relationships
            if r.from_character == character or r.to_character == character
        ]

    def get_faction_for(self, character: str) -> Faction | None:
        """Get the faction a character belongs to."""
        for faction in self.factions:
            if character in faction.members:
                return faction
        return None
