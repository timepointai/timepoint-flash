"""Tests for generation schemas.

Tests:
    - JudgeResult validation
    - TimelineData validation
    - SceneData validation
    - CharacterData validation (max 8)
    - DialogData validation (max 7)
    - ImagePromptData validation
"""

import pytest

from app.schemas import (
    CameraData,
    Character,
    CharacterData,
    CharacterRole,
    DialogData,
    DialogLine,
    Faction,
    GraphData,
    ImagePromptData,
    JudgeResult,
    MomentData,
    QueryType,
    Relationship,
    SceneData,
    SensoryDetail,
    TimelineData,
)


# JudgeResult Tests


@pytest.mark.fast
class TestJudgeResult:
    """Tests for JudgeResult schema."""

    def test_valid_judge_result(self):
        """Test creating a valid judge result."""
        result = JudgeResult(
            is_valid=True,
            query_type=QueryType.HISTORICAL,
            cleaned_query="The signing of the Declaration of Independence",
            confidence=0.95,
        )
        assert result.is_valid is True
        assert result.query_type == QueryType.HISTORICAL
        assert result.confidence == 0.95

    def test_invalid_judge_result(self):
        """Test creating an invalid judge result."""
        result = JudgeResult(
            is_valid=False,
            query_type=QueryType.INVALID,
            reason="Query is too vague",
            suggested_query="Try 'Rome in 50 BCE'",
        )
        assert result.is_valid is False
        assert result.reason is not None

    def test_judge_result_with_detections(self):
        """Test judge result with detected entities."""
        result = JudgeResult(
            is_valid=True,
            query_type=QueryType.HISTORICAL,
            cleaned_query="Rome",
            detected_year=-50,
            detected_location="Rome",
            detected_figures=["Julius Caesar", "Pompey"],
        )
        assert result.detected_year == -50
        assert len(result.detected_figures) == 2

    def test_query_type_enum(self):
        """Test QueryType enum values."""
        assert QueryType.HISTORICAL.value == "historical"
        assert QueryType.FICTIONAL.value == "fictional"
        assert QueryType.SPECULATIVE.value == "speculative"
        assert QueryType.CONTEMPORARY.value == "contemporary"
        assert QueryType.INVALID.value == "invalid"

    def test_confidence_bounds(self):
        """Test confidence value bounds."""
        # Valid bounds
        JudgeResult(is_valid=True, confidence=0.0)
        JudgeResult(is_valid=True, confidence=1.0)
        JudgeResult(is_valid=True, confidence=0.5)

        # Invalid bounds
        with pytest.raises(ValueError):
            JudgeResult(is_valid=True, confidence=-0.1)
        with pytest.raises(ValueError):
            JudgeResult(is_valid=True, confidence=1.1)


# TimelineData Tests


@pytest.mark.fast
class TestTimelineData:
    """Tests for TimelineData schema."""

    def test_valid_timeline_data(self):
        """Test creating valid timeline data."""
        data = TimelineData(
            year=1776,
            month=7,
            day=4,
            season="summer",
            time_of_day="afternoon",
            location="Independence Hall, Philadelphia",
            era="American Revolution",
        )
        assert data.year == 1776
        assert data.location == "Independence Hall, Philadelphia"
        assert data.display_year == "1776 CE"

    def test_timeline_data_bce(self):
        """Test BCE timeline data."""
        data = TimelineData(year=-44, month=3, day=15, location="Roman Senate")
        assert data.is_bce is True
        assert data.display_year == "44 BCE"

    def test_timeline_data_season_normalization(self):
        """Test season normalization."""
        data = TimelineData(year=2000, season="autumn", location="Test")
        assert data.season == "fall"

    def test_timeline_to_temporal_dict(self):
        """Test conversion to temporal dictionary."""
        data = TimelineData(
            year=1776,
            month=7,
            day=4,
            season="summer",
            location="Philadelphia",
            era="Revolution",
        )
        d = data.to_temporal_dict()
        assert d["year"] == 1776
        assert d["month"] == 7
        assert d["location"] == "Philadelphia"


# SceneData Tests


@pytest.mark.fast
class TestSceneData:
    """Tests for SceneData schema."""

    def test_valid_scene_data(self):
        """Test creating valid scene data."""
        scene = SceneData(
            setting="The Assembly Room of Independence Hall",
            atmosphere="Tense anticipation mixed with revolutionary fervor",
            weather="Hot and humid",
            lighting="Afternoon sunlight through tall windows",
            tension_level="high",
        )
        assert scene.setting is not None
        assert scene.tension_level == "high"

    def test_scene_with_sensory_details(self):
        """Test scene with sensory details."""
        scene = SceneData(
            setting="Test setting",
            atmosphere="Test atmosphere",
            sensory_details=[
                SensoryDetail(sense="sight", description="Flickering candles", intensity="moderate"),
                SensoryDetail(sense="sound", description="Quill scratching", intensity="subtle"),
            ],
        )
        assert len(scene.sensory_details) == 2

    def test_get_sensory_by_type(self):
        """Test filtering sensory details by type."""
        scene = SceneData(
            setting="Test",
            atmosphere="Test",
            sensory_details=[
                SensoryDetail(sense="sight", description="Test 1"),
                SensoryDetail(sense="sight", description="Test 2"),
                SensoryDetail(sense="sound", description="Test 3"),
            ],
        )
        sight_details = scene.get_sensory_by_type("sight")
        assert len(sight_details) == 2

    def test_scene_to_description(self):
        """Test converting scene to description."""
        scene = SceneData(
            setting="Independence Hall",
            atmosphere="Revolutionary",
            weather="Hot",
            lighting="Bright",
        )
        desc = scene.to_description()
        assert "Independence Hall" in desc
        assert "Revolutionary" in desc


# CharacterData Tests


@pytest.mark.fast
class TestCharacterData:
    """Tests for CharacterData schema."""

    def test_valid_character(self):
        """Test creating a valid character."""
        char = Character(
            name="John Hancock",
            role=CharacterRole.PRIMARY,
            description="Tall man with commanding presence",
            clothing="Fine colonial attire",
            expression="Determined",
        )
        assert char.name == "John Hancock"
        assert char.role == CharacterRole.PRIMARY

    def test_character_to_prompt_description(self):
        """Test character prompt description."""
        char = Character(
            name="Benjamin Franklin",
            role=CharacterRole.PRIMARY,
            description="Elderly statesman",
            clothing="Simple coat",
            expression="Amused",
        )
        desc = char.to_prompt_description()
        assert "Benjamin Franklin" in desc
        assert "elderly statesman" in desc.lower()

    def test_character_data_max_eight(self):
        """Test that CharacterData limits to 8 characters."""
        characters = [
            Character(name=f"Char {i}", role=CharacterRole.BACKGROUND, description=f"Desc {i}")
            for i in range(12)
        ]
        data = CharacterData(characters=characters)
        assert len(data.characters) == 8

    def test_character_role_filtering(self):
        """Test filtering characters by role."""
        data = CharacterData(
            characters=[
                Character(name="Primary 1", role=CharacterRole.PRIMARY, description="Test"),
                Character(name="Secondary 1", role=CharacterRole.SECONDARY, description="Test"),
                Character(name="Background 1", role=CharacterRole.BACKGROUND, description="Test"),
            ]
        )
        assert len(data.primary_characters) == 1
        assert len(data.secondary_characters) == 1
        assert len(data.background_characters) == 1

    def test_get_character_by_name(self):
        """Test finding character by name."""
        data = CharacterData(
            characters=[
                Character(name="John Adams", role=CharacterRole.PRIMARY, description="Test"),
                Character(name="Thomas Jefferson", role=CharacterRole.PRIMARY, description="Test"),
            ]
        )
        john = data.get_character_by_name("john adams")
        assert john is not None
        assert john.name == "John Adams"


# DialogData Tests


@pytest.mark.fast
class TestDialogData:
    """Tests for DialogData schema."""

    def test_valid_dialog_line(self):
        """Test creating a valid dialog line."""
        line = DialogLine(
            speaker="John Hancock",
            text="Gentlemen, the question is before you.",
            tone="formal",
        )
        assert line.speaker == "John Hancock"
        assert line.tone == "formal"

    def test_dialog_line_to_script_format(self):
        """Test converting dialog line to script format."""
        line = DialogLine(
            speaker="Franklin",
            text="We must hang together.",
            tone="wry",
            action="smiles",
        )
        script = line.to_script_format()
        assert "FRANKLIN" in script
        assert "We must hang together" in script

    def test_dialog_data_max_seven(self):
        """Test that DialogData limits to 7 lines."""
        lines = [
            DialogLine(speaker=f"Speaker {i}", text=f"Line {i}")
            for i in range(10)
        ]
        data = DialogData(lines=lines)
        assert len(data.lines) == 7

    def test_dialog_speakers(self):
        """Test getting unique speakers."""
        data = DialogData(
            lines=[
                DialogLine(speaker="Adams", text="Line 1"),
                DialogLine(speaker="Jefferson", text="Line 2"),
                DialogLine(speaker="Adams", text="Line 3"),
            ]
        )
        speakers = data.speakers
        assert len(speakers) == 2
        assert "Adams" in speakers
        assert "Jefferson" in speakers

    def test_dialog_to_script(self):
        """Test converting dialog to full script."""
        data = DialogData(
            lines=[
                DialogLine(speaker="Adams", text="The die is cast."),
                DialogLine(speaker="Franklin", text="Indeed."),
            ],
            scene_context="The signing ceremony",
        )
        script = data.to_script()
        assert "ADAMS" in script
        assert "FRANKLIN" in script


# ImagePromptData Tests


@pytest.mark.fast
class TestImagePromptData:
    """Tests for ImagePromptData schema."""

    def test_valid_image_prompt(self):
        """Test creating valid image prompt data."""
        prompt = ImagePromptData(
            full_prompt="A photorealistic scene of Independence Hall...",
            style="photorealistic historical painting",
            aspect_ratio="16:9",
        )
        assert prompt.full_prompt is not None
        assert prompt.style == "photorealistic historical painting"

    def test_image_prompt_length(self):
        """Test prompt length property."""
        prompt = ImagePromptData(
            full_prompt="A" * 5000,
            style="test",
        )
        assert prompt.prompt_length == 5000
        assert prompt.is_within_limit is True

    def test_image_prompt_exceeds_limit(self):
        """Test prompt exceeding typical limit."""
        prompt = ImagePromptData(
            full_prompt="A" * 12000,
            style="test",
        )
        assert prompt.is_within_limit is False

    def test_get_enhanced_prompt(self):
        """Test getting prompt with quality tags."""
        prompt = ImagePromptData(
            full_prompt="Test prompt",
            style="test",
            quality_tags=["highly detailed", "8k"],
        )
        enhanced = prompt.get_enhanced_prompt()
        assert "Test prompt" in enhanced
        assert "highly detailed" in enhanced
        assert "8k" in enhanced

    def test_to_generation_params(self):
        """Test converting to generation parameters."""
        prompt = ImagePromptData(
            full_prompt="Test prompt",
            style="test",
            aspect_ratio="16:9",
            negative_prompt="blurry",
        )
        params = prompt.to_generation_params()
        assert "prompt" in params
        assert params["aspect_ratio"] == "16:9"
        assert params["negative_prompt"] == "blurry"


# MomentData Tests


@pytest.mark.fast
class TestMomentData:
    """Tests for MomentData schema."""

    def test_valid_moment_data(self):
        """Test creating valid moment data."""
        moment = MomentData(
            plot_summary="The delegates prepare to sign the declaration",
            stakes="The future of American independence",
            tension_arc="climactic",
        )
        assert moment.plot_summary is not None
        assert moment.stakes == "The future of American independence"
        assert moment.is_climactic is True

    def test_moment_with_emotional_beats(self):
        """Test moment with emotional beats."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="rising",
            emotional_beats=["anticipation", "resolve", "fear"],
        )
        assert len(moment.emotional_beats) == 3

    def test_moment_to_narrative(self):
        """Test converting moment to narrative."""
        moment = MomentData(
            plot_summary="The signing begins",
            stakes="Liberty or death",
            tension_arc="high",
        )
        narrative = moment.to_narrative()
        assert "signing begins" in narrative
        assert "Liberty or death" in narrative


# CameraData Tests


@pytest.mark.fast
class TestCameraData:
    """Tests for CameraData schema."""

    def test_valid_camera_data(self):
        """Test creating valid camera data."""
        camera = CameraData(
            shot_type="wide establishing",
            angle="eye level",
            focal_point="The signing table",
            depth_of_field="deep",
        )
        assert camera.shot_type == "wide establishing"
        assert camera.focal_point == "The signing table"

    def test_camera_with_layers(self):
        """Test camera with foreground/background."""
        camera = CameraData(
            focal_point="Main action",
            foreground_elements=["quill", "inkwell"],
            midground_elements=["signers"],
            background_elements=["windows", "flags"],
        )
        assert len(camera.foreground_elements) == 2
        assert len(camera.background_elements) == 2

    def test_camera_to_description(self):
        """Test converting camera to description."""
        camera = CameraData(
            shot_type="medium",
            angle="low angle",
            focal_point="Hancock",
            composition_rule="rule of thirds",
        )
        desc = camera.to_description()
        assert "medium" in desc
        assert "low angle" in desc
        assert "Hancock" in desc


# GraphData Tests


@pytest.mark.fast
class TestGraphData:
    """Tests for GraphData schema."""

    def test_valid_relationship(self):
        """Test creating a valid relationship."""
        rel = Relationship(
            from_character="John Adams",
            to_character="Thomas Jefferson",
            relationship_type="ally",
            tension_level="friendly",
        )
        assert rel.from_character == "John Adams"
        assert rel.relationship_type == "ally"

    def test_relationship_to_edge(self):
        """Test converting relationship to edge."""
        rel = Relationship(
            from_character="A",
            to_character="B",
            relationship_type="rival",
        )
        edge = rel.to_edge()
        assert edge == ("A", "B", "rival")

    def test_valid_faction(self):
        """Test creating a valid faction."""
        faction = Faction(
            name="Patriots",
            members=["Adams", "Franklin", "Jefferson"],
            goal="Independence",
        )
        assert faction.name == "Patriots"
        assert len(faction.members) == 3

    def test_graph_data_with_relationships(self):
        """Test graph data with relationships."""
        graph = GraphData(
            relationships=[
                Relationship(from_character="A", to_character="B", relationship_type="ally"),
                Relationship(from_character="B", to_character="C", relationship_type="rival"),
            ],
            factions=[
                Faction(name="Group 1", members=["A", "B"]),
            ],
        )
        assert len(graph.relationships) == 2
        assert len(graph.factions) == 1

    def test_get_relationships_for(self):
        """Test getting relationships for a character."""
        graph = GraphData(
            relationships=[
                Relationship(from_character="A", to_character="B", relationship_type="ally"),
                Relationship(from_character="C", to_character="A", relationship_type="mentor"),
                Relationship(from_character="B", to_character="C", relationship_type="rival"),
            ],
        )
        a_rels = graph.get_relationships_for("A")
        assert len(a_rels) == 2

    def test_get_faction_for(self):
        """Test getting faction for a character."""
        graph = GraphData(
            factions=[
                Faction(name="Patriots", members=["Adams", "Franklin"]),
                Faction(name="Loyalists", members=["Arnold"]),
            ],
        )
        faction = graph.get_faction_for("Franklin")
        assert faction is not None
        assert faction.name == "Patriots"

        no_faction = graph.get_faction_for("Unknown")
        assert no_faction is None
