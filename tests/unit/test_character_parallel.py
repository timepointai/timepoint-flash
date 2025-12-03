"""Tests for parallel character generation (Phase 11).

Tests for:
- CharacterStub schema
- CharacterIdentification schema
- CharacterIdentificationAgent input/output
- CharacterBioAgent input/output
- Fallback character creation
"""

import pytest

from app.schemas import CharacterRole
from app.schemas.character_identification import CharacterIdentification, CharacterStub
from app.agents.character_bio import (
    CharacterBioAgent,
    CharacterBioInput,
    create_fallback_character,
)
from app.agents.character_identification import (
    CharacterIdentificationAgent,
    CharacterIdentificationInput,
)


# CharacterStub Tests


@pytest.mark.fast
class TestCharacterStub:
    """Tests for CharacterStub schema."""

    def test_valid_stub(self):
        """Test creating a valid character stub."""
        stub = CharacterStub(
            name="Julius Caesar",
            role=CharacterRole.PRIMARY,
            brief_description="Roman dictator at moment of assassination",
            speaks_in_scene=True,
            key_relationships=["Brutus", "Cassius"],
        )
        assert stub.name == "Julius Caesar"
        assert stub.role == CharacterRole.PRIMARY
        assert stub.speaks_in_scene is True
        assert len(stub.key_relationships) == 2

    def test_stub_defaults(self):
        """Test stub default values."""
        stub = CharacterStub(
            name="Background Guard",
            brief_description="Roman soldier standing guard",
        )
        assert stub.role == CharacterRole.SECONDARY
        assert stub.speaks_in_scene is False
        assert stub.key_relationships == []

    def test_stub_minimal(self):
        """Test minimal stub creation."""
        stub = CharacterStub(
            name="Unnamed Senator",
            brief_description="Elder statesman observing",
        )
        assert stub.name == "Unnamed Senator"


# CharacterIdentification Tests


@pytest.mark.fast
class TestCharacterIdentification:
    """Tests for CharacterIdentification schema."""

    def test_valid_identification(self):
        """Test creating valid character identification."""
        stubs = [
            CharacterStub(
                name="Caesar",
                role=CharacterRole.PRIMARY,
                brief_description="Roman dictator",
                speaks_in_scene=True,
            ),
            CharacterStub(
                name="Brutus",
                role=CharacterRole.PRIMARY,
                brief_description="Senator and conspirator",
                speaks_in_scene=True,
                key_relationships=["Caesar"],
            ),
            CharacterStub(
                name="Guard",
                role=CharacterRole.BACKGROUND,
                brief_description="Roman soldier",
            ),
        ]
        char_id = CharacterIdentification(
            characters=stubs,
            focal_character="Caesar",
            group_dynamics="Conspirators surrounding their target",
        )
        assert len(char_id.characters) == 3
        assert char_id.focal_character == "Caesar"

    def test_max_characters_enforced(self):
        """Test that CharacterIdentification limits to 8 characters."""
        stubs = [
            CharacterStub(
                name=f"Character {i}",
                role=CharacterRole.BACKGROUND,
                brief_description=f"Background character {i}",
            )
            for i in range(12)
        ]
        char_id = CharacterIdentification(
            characters=stubs,
            focal_character="Character 0",
            group_dynamics="Large crowd",
        )
        assert len(char_id.characters) == 8

    def test_primary_stubs_property(self):
        """Test primary_stubs property."""
        stubs = [
            CharacterStub(name="Primary 1", role=CharacterRole.PRIMARY, brief_description="Test"),
            CharacterStub(name="Secondary 1", role=CharacterRole.SECONDARY, brief_description="Test"),
            CharacterStub(name="Background 1", role=CharacterRole.BACKGROUND, brief_description="Test"),
        ]
        char_id = CharacterIdentification(
            characters=stubs,
            focal_character="Primary 1",
            group_dynamics="Test",
        )
        assert len(char_id.primary_stubs) == 1
        assert char_id.primary_stubs[0].name == "Primary 1"

    def test_speaking_stubs_property(self):
        """Test speaking_stubs property."""
        stubs = [
            CharacterStub(name="Speaker 1", role=CharacterRole.PRIMARY, brief_description="Test", speaks_in_scene=True),
            CharacterStub(name="Speaker 2", role=CharacterRole.SECONDARY, brief_description="Test", speaks_in_scene=True),
            CharacterStub(name="Silent 1", role=CharacterRole.BACKGROUND, brief_description="Test", speaks_in_scene=False),
        ]
        char_id = CharacterIdentification(
            characters=stubs,
            focal_character="Speaker 1",
            group_dynamics="Test",
        )
        assert len(char_id.speaking_stubs) == 2

    def test_get_cast_context(self):
        """Test get_cast_context method."""
        stubs = [
            CharacterStub(
                name="Caesar",
                role=CharacterRole.PRIMARY,
                brief_description="Roman dictator",
                speaks_in_scene=True,
                key_relationships=["Brutus"],
            ),
            CharacterStub(
                name="Brutus",
                role=CharacterRole.PRIMARY,
                brief_description="Senator and conspirator",
                speaks_in_scene=True,
                key_relationships=["Caesar"],
            ),
        ]
        char_id = CharacterIdentification(
            characters=stubs,
            focal_character="Caesar",
            group_dynamics="Assassination plot",
        )
        context = char_id.get_cast_context()
        assert "FULL CAST:" in context
        assert "Caesar (PRIMARY)" in context
        assert "[SPEAKS]" in context
        assert "FOCAL CHARACTER: Caesar" in context
        assert "GROUP DYNAMICS: Assassination plot" in context


# CharacterIdentificationInput Tests


@pytest.mark.fast
class TestCharacterIdentificationInput:
    """Tests for CharacterIdentificationInput."""

    def test_valid_input(self):
        """Test creating valid input."""
        input_data = CharacterIdentificationInput(
            query="assassination of Julius Caesar",
            year=-44,
            era="Roman Republic",
            location="Roman Senate",
            setting="Interior of the Theatre of Pompey",
            atmosphere="Tense and conspiratorial",
            tension_level="high",
            detected_figures=["Julius Caesar", "Brutus", "Cassius"],
        )
        assert input_data.query == "assassination of Julius Caesar"
        assert input_data.year == -44
        assert len(input_data.detected_figures) == 3

    def test_input_defaults(self):
        """Test input default values."""
        input_data = CharacterIdentificationInput(
            query="test query",
            year=1776,
        )
        assert input_data.era is None
        assert input_data.location == ""
        assert input_data.detected_figures == []
        assert input_data.tension_level == "medium"


# CharacterBioInput Tests


@pytest.mark.fast
class TestCharacterBioInput:
    """Tests for CharacterBioInput."""

    def test_valid_input(self):
        """Test creating valid bio input."""
        stub = CharacterStub(
            name="Caesar",
            role=CharacterRole.PRIMARY,
            brief_description="Roman dictator",
            speaks_in_scene=True,
            key_relationships=["Brutus"],
        )
        full_cast = CharacterIdentification(
            characters=[stub],
            focal_character="Caesar",
            group_dynamics="Test",
        )
        input_data = CharacterBioInput(
            stub=stub,
            full_cast=full_cast,
            query="assassination of Caesar",
            year=-44,
            era="Roman Republic",
            location="Roman Senate",
            setting="Theatre of Pompey",
            atmosphere="Tense",
            tension_level="high",
        )
        assert input_data.stub.name == "Caesar"
        assert input_data.full_cast.focal_character == "Caesar"

    def test_from_identification_factory(self):
        """Test from_identification factory method."""
        stub = CharacterStub(
            name="Franklin",
            role=CharacterRole.PRIMARY,
            brief_description="Elder statesman",
            speaks_in_scene=True,
        )
        full_cast = CharacterIdentification(
            characters=[stub],
            focal_character="Franklin",
            group_dynamics="Founding fathers",
        )
        input_data = CharacterBioInput.from_identification(
            stub=stub,
            full_cast=full_cast,
            query="signing declaration",
            year=1776,
            era="American Revolution",
            location="Philadelphia",
            setting="Independence Hall",
            atmosphere="Momentous",
            tension_level="high",
        )
        assert input_data.stub == stub
        assert input_data.year == 1776


# Fallback Character Tests


@pytest.mark.fast
class TestFallbackCharacter:
    """Tests for fallback character creation."""

    def test_create_fallback_from_stub(self):
        """Test creating fallback character from stub."""
        stub = CharacterStub(
            name="Unknown Senator",
            role=CharacterRole.SECONDARY,
            brief_description="Observing the proceedings",
            speaks_in_scene=False,
        )
        character = create_fallback_character(stub)
        assert character.name == "Unknown Senator"
        assert character.role == CharacterRole.SECONDARY
        assert character.description == "Observing the proceedings"
        assert character.speaks_in_scene is False
        assert character.clothing == "Period-appropriate attire"

    def test_fallback_with_speaking(self):
        """Test fallback character that speaks."""
        stub = CharacterStub(
            name="Speaker",
            role=CharacterRole.PRIMARY,
            brief_description="Main speaker",
            speaks_in_scene=True,
        )
        character = create_fallback_character(stub)
        assert character.speaks_in_scene is True


# Agent Initialization Tests


@pytest.mark.fast
class TestAgentInitialization:
    """Tests for agent initialization."""

    def test_char_id_agent_init(self):
        """Test CharacterIdentificationAgent initialization."""
        agent = CharacterIdentificationAgent()
        assert agent.name == "CharacterIdentificationAgent"
        assert agent.response_model == CharacterIdentification

    def test_char_bio_agent_init(self):
        """Test CharacterBioAgent initialization."""
        from app.schemas import Character
        agent = CharacterBioAgent()
        assert agent.name == "CharacterBioAgent"
        assert agent.response_model == Character

    def test_agents_have_system_prompts(self):
        """Test that agents have system prompts."""
        id_agent = CharacterIdentificationAgent()
        bio_agent = CharacterBioAgent()

        assert id_agent.get_system_prompt() is not None
        assert len(id_agent.get_system_prompt()) > 100

        assert bio_agent.get_system_prompt() is not None
        assert len(bio_agent.get_system_prompt()) > 100


# Prompt Tests


@pytest.mark.fast
class TestPrompts:
    """Tests for prompt templates."""

    def test_char_id_prompt(self):
        """Test character identification prompt generation."""
        from app.prompts import character_identification

        prompt = character_identification.get_prompt(
            query="assassination of Caesar",
            year=-44,
            era="Roman Republic",
            location="Rome",
            setting="Theatre of Pompey",
            atmosphere="Tense",
            tension_level="high",
            detected_figures=["Caesar", "Brutus"],
        )
        assert "assassination of Caesar" in prompt
        assert "44 BCE" in prompt
        assert "Caesar, Brutus" in prompt

    def test_char_bio_prompt(self):
        """Test character bio prompt generation."""
        from app.prompts import character_bio

        prompt = character_bio.get_prompt(
            character_name="Julius Caesar",
            character_role="primary",
            character_brief="Roman dictator at moment of assassination",
            speaks_in_scene=True,
            key_relationships=["Brutus", "Cassius"],
            cast_context="FULL CAST: ...",
            query="assassination",
            year=-44,
            era="Roman Republic",
            location="Rome",
            setting="Theatre",
            atmosphere="Tense",
            tension_level="high",
        )
        assert "Julius Caesar" in prompt
        assert "primary" in prompt
        assert "Brutus, Cassius" in prompt
        assert "44 BCE" in prompt

    def test_char_bio_prompt_no_relationships(self):
        """Test bio prompt with no relationships."""
        from app.prompts import character_bio

        prompt = character_bio.get_prompt(
            character_name="Background Guard",
            character_role="background",
            character_brief="Roman soldier",
            speaks_in_scene=False,
            key_relationships=[],
            cast_context="",
            query="test",
            year=100,
            era=None,
            location="Rome",
            setting="Test",
            atmosphere="Test",
            tension_level="low",
        )
        assert "Background Guard" in prompt
        assert "None" in prompt  # No relationships
