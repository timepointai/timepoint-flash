"""Unit tests for narrative arc dialog system.

Tests the DialogArc schema, build_arc_from_moment factory,
and Vonnegut/Freytag narrative shape mappings.

Run with:
    pytest tests/unit/test_dialog_arc.py -v
    pytest tests/unit/test_dialog_arc.py -v -m fast
"""

import pytest

from app.schemas.dialog_arc import (
    ArcBeat,
    BEAT_STRUCTURES,
    DEFAULT_EMOTIONAL_BEATS,
    DialogArc,
    INTENSITY_CURVES,
    NarrativeFunction,
    NarrativeShape,
    TENSION_ARC_TO_SHAPE,
    build_arc_from_moment,
)
from app.schemas.moment import MomentData


@pytest.mark.fast
class TestNarrativeShape:
    """Tests for NarrativeShape enum."""

    def test_all_shapes_exist(self):
        """Test all 6 narrative shapes are defined."""
        shapes = list(NarrativeShape)
        assert len(shapes) == 6
        assert NarrativeShape.MAN_IN_HOLE in shapes
        assert NarrativeShape.CREATION in shapes
        assert NarrativeShape.CINDERELLA in shapes
        assert NarrativeShape.FROM_BAD_TO_WORSE in shapes
        assert NarrativeShape.OLD_TESTAMENT in shapes
        assert NarrativeShape.FREYTAG in shapes

    def test_shapes_are_strings(self):
        """Test shapes are string enums."""
        assert NarrativeShape.FREYTAG.value == "freytag"
        assert NarrativeShape.MAN_IN_HOLE.value == "man_in_hole"


@pytest.mark.fast
class TestNarrativeFunction:
    """Tests for NarrativeFunction enum."""

    def test_all_functions_exist(self):
        """Test all 7 narrative functions are defined."""
        funcs = list(NarrativeFunction)
        assert len(funcs) == 7
        assert NarrativeFunction.ESTABLISH in funcs
        assert NarrativeFunction.COMPLICATE in funcs
        assert NarrativeFunction.ESCALATE in funcs
        assert NarrativeFunction.TURN in funcs
        assert NarrativeFunction.REACT in funcs
        assert NarrativeFunction.RESOLVE in funcs
        assert NarrativeFunction.PUNCTUATE in funcs


@pytest.mark.fast
class TestArcBeat:
    """Tests for ArcBeat model."""

    def test_create_beat(self):
        """Test creating a basic arc beat."""
        beat = ArcBeat(
            position=0,
            narrative_function=NarrativeFunction.ESTABLISH,
            emotional_target="anticipation",
            speaker_role="primary",
            intensity=0.3,
        )
        assert beat.position == 0
        assert beat.narrative_function == NarrativeFunction.ESTABLISH
        assert beat.emotional_target == "anticipation"
        assert beat.intensity == 0.3

    def test_beat_defaults(self):
        """Test ArcBeat default values."""
        beat = ArcBeat(position=3, narrative_function=NarrativeFunction.TURN)
        assert beat.emotional_target == "neutral"
        assert beat.speaker_role == "primary"
        assert beat.intensity == 0.5

    def test_beat_intensity_bounds(self):
        """Test intensity is bounded 0.0-1.0."""
        beat = ArcBeat(position=0, narrative_function=NarrativeFunction.ESTABLISH, intensity=0.0)
        assert beat.intensity == 0.0
        beat = ArcBeat(position=0, narrative_function=NarrativeFunction.ESTABLISH, intensity=1.0)
        assert beat.intensity == 1.0

    def test_beat_position_bounds(self):
        """Test position is bounded 0-6."""
        beat = ArcBeat(position=0, narrative_function=NarrativeFunction.ESTABLISH)
        assert beat.position == 0
        beat = ArcBeat(position=6, narrative_function=NarrativeFunction.PUNCTUATE)
        assert beat.position == 6


@pytest.mark.fast
class TestDialogArc:
    """Tests for DialogArc model."""

    def _make_beats(self) -> list[ArcBeat]:
        """Create 7 test beats."""
        return [
            ArcBeat(position=i, narrative_function=NarrativeFunction.ESTABLISH)
            for i in range(7)
        ]

    def test_create_arc(self):
        """Test creating a DialogArc."""
        arc = DialogArc(
            shape=NarrativeShape.FREYTAG,
            beats=self._make_beats(),
            central_question="Will they sign?",
            arc_summary="freytag: building to signing moment",
        )
        assert arc.shape == NarrativeShape.FREYTAG
        assert len(arc.beats) == 7
        assert arc.central_question == "Will they sign?"

    def test_arc_requires_7_beats(self):
        """Test that arc requires exactly 7 beats."""
        with pytest.raises(Exception):
            DialogArc(
                shape=NarrativeShape.FREYTAG,
                beats=[ArcBeat(position=0, narrative_function=NarrativeFunction.ESTABLISH)],
            )


@pytest.mark.fast
class TestIntensityCurves:
    """Tests for intensity curve data."""

    def test_all_shapes_have_curves(self):
        """Test every shape has an intensity curve."""
        for shape in NarrativeShape:
            assert shape in INTENSITY_CURVES, f"Missing curve for {shape}"
            assert len(INTENSITY_CURVES[shape]) == 7

    def test_intensity_values_in_range(self):
        """Test all intensity values are 0.0-1.0."""
        for shape, curve in INTENSITY_CURVES.items():
            for val in curve:
                assert 0.0 <= val <= 1.0, f"Out of range: {shape} has {val}"

    def test_freytag_peaks_at_position_4(self):
        """Test Freytag pyramid peaks at the climax position."""
        curve = INTENSITY_CURVES[NarrativeShape.FREYTAG]
        assert curve[4] == max(curve)


@pytest.mark.fast
class TestBeatStructures:
    """Tests for beat structure data."""

    def test_all_shapes_have_structures(self):
        """Test every shape has a beat structure."""
        for shape in NarrativeShape:
            assert shape in BEAT_STRUCTURES, f"Missing structure for {shape}"
            assert len(BEAT_STRUCTURES[shape]) == 7

    def test_freytag_has_turn(self):
        """Test Freytag structure contains TURN."""
        funcs = BEAT_STRUCTURES[NarrativeShape.FREYTAG]
        assert NarrativeFunction.TURN in funcs

    def test_all_structures_start_with_establish(self):
        """Test all structures start with ESTABLISH."""
        for shape, funcs in BEAT_STRUCTURES.items():
            assert funcs[0] == NarrativeFunction.ESTABLISH, f"{shape} doesn't start with ESTABLISH"


@pytest.mark.fast
class TestDefaultEmotionalBeats:
    """Tests for default emotional beat data."""

    def test_all_shapes_have_defaults(self):
        """Test every shape has default emotional beats."""
        for shape in NarrativeShape:
            assert shape in DEFAULT_EMOTIONAL_BEATS, f"Missing defaults for {shape}"
            assert len(DEFAULT_EMOTIONAL_BEATS[shape]) == 7

    def test_defaults_are_strings(self):
        """Test all defaults are non-empty strings."""
        for shape, beats in DEFAULT_EMOTIONAL_BEATS.items():
            for beat in beats:
                assert isinstance(beat, str) and beat, f"Empty beat in {shape}"


@pytest.mark.fast
class TestTensionArcMapping:
    """Tests for tension_arc to shape mapping."""

    def test_climactic_maps_to_freytag(self):
        assert TENSION_ARC_TO_SHAPE["climactic"] == NarrativeShape.FREYTAG

    def test_rising_maps_to_creation(self):
        assert TENSION_ARC_TO_SHAPE["rising"] == NarrativeShape.CREATION

    def test_falling_maps_to_old_testament(self):
        assert TENSION_ARC_TO_SHAPE["falling"] == NarrativeShape.OLD_TESTAMENT

    def test_resolved_maps_to_man_in_hole(self):
        assert TENSION_ARC_TO_SHAPE["resolved"] == NarrativeShape.MAN_IN_HOLE


@pytest.mark.fast
class TestBuildArcFromMoment:
    """Tests for build_arc_from_moment factory function."""

    def test_climactic_moment(self):
        """Test building arc from climactic tension arc."""
        moment = MomentData(
            plot_summary="The climactic signing",
            stakes="American independence",
            tension_arc="climactic",
            central_question="Will they sign?",
        )
        arc = build_arc_from_moment(moment)
        assert arc.shape == NarrativeShape.FREYTAG
        assert len(arc.beats) == 7
        assert arc.central_question == "Will they sign?"

    def test_rising_moment(self):
        """Test building arc from rising tension arc."""
        moment = MomentData(
            plot_summary="Apollo 11 launch",
            stakes="Space exploration",
            tension_arc="rising",
        )
        arc = build_arc_from_moment(moment)
        assert arc.shape == NarrativeShape.CREATION

    def test_falling_moment(self):
        """Test building arc from falling tension arc."""
        moment = MomentData(
            plot_summary="The fall of Sarajevo",
            stakes="Civilization",
            tension_arc="falling",
        )
        arc = build_arc_from_moment(moment)
        assert arc.shape == NarrativeShape.OLD_TESTAMENT

    def test_resolved_moment(self):
        """Test building arc from resolved tension arc."""
        moment = MomentData(
            plot_summary="Peace treaty signed",
            stakes="End of war",
            tension_arc="resolved",
        )
        arc = build_arc_from_moment(moment)
        assert arc.shape == NarrativeShape.MAN_IN_HOLE

    def test_unknown_tension_arc_defaults_to_freytag(self):
        """Test unknown tension_arc defaults to Freytag."""
        moment = MomentData(
            plot_summary="Something happens",
            tension_arc="unknown_type",
        )
        arc = build_arc_from_moment(moment)
        assert arc.shape == NarrativeShape.FREYTAG

    def test_emotional_beats_from_moment(self):
        """Test emotional beats are pulled from moment data."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="climactic",
            emotional_beats=["joy", "fear", "anger", "hope", "dread", "relief", "peace"],
        )
        arc = build_arc_from_moment(moment)
        assert arc.beats[0].emotional_target == "joy"
        assert arc.beats[4].emotional_target == "dread"
        assert arc.beats[6].emotional_target == "peace"

    def test_emotional_beats_padded_with_defaults(self):
        """Test short emotional_beats list is padded with defaults."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="climactic",
            emotional_beats=["joy", "fear"],
        )
        arc = build_arc_from_moment(moment)
        assert arc.beats[0].emotional_target == "joy"
        assert arc.beats[1].emotional_target == "fear"
        # Rest should be defaults
        assert arc.beats[2].emotional_target == DEFAULT_EMOTIONAL_BEATS[NarrativeShape.FREYTAG][2]

    def test_intensity_curve_applied(self):
        """Test intensity curve is applied to beats."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="climactic",
        )
        arc = build_arc_from_moment(moment)
        expected = INTENSITY_CURVES[NarrativeShape.FREYTAG]
        for i, beat in enumerate(arc.beats):
            assert beat.intensity == expected[i]

    def test_speaker_roles_assigned(self):
        """Test speaker roles are assigned per narrative function."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="climactic",
        )
        arc = build_arc_from_moment(moment)
        # TURN beat should be primary speaker
        turn_beats = [b for b in arc.beats if b.narrative_function == NarrativeFunction.TURN]
        assert all(b.speaker_role == "primary" for b in turn_beats)
        # PUNCTUATE should be background
        punct_beats = [b for b in arc.beats if b.narrative_function == NarrativeFunction.PUNCTUATE]
        assert all(b.speaker_role == "background" for b in punct_beats)

    def test_arc_summary_includes_stakes(self):
        """Test arc summary includes stakes when present."""
        moment = MomentData(
            plot_summary="Test",
            tension_arc="rising",
            stakes="Everything is at stake",
        )
        arc = build_arc_from_moment(moment)
        assert "Everything is at stake" in arc.arc_summary

    def test_all_tension_arcs_produce_valid_arcs(self):
        """Test all mapped tension arcs produce valid 7-beat arcs."""
        for tension_arc in TENSION_ARC_TO_SHAPE:
            moment = MomentData(
                plot_summary=f"Test {tension_arc}",
                tension_arc=tension_arc,
            )
            arc = build_arc_from_moment(moment)
            assert len(arc.beats) == 7
            assert arc.shape == TENSION_ARC_TO_SHAPE[tension_arc]
            # Verify positions are 0-6
            for i, beat in enumerate(arc.beats):
                assert beat.position == i
