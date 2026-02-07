"""Narrative arc schema for dialog structure.

Implements Vonnegut's story shapes + Freytag's pyramid to constrain
7 dialog lines into a coherent micro-story. Forces dialog complexity
to O(n) instead of O(2^n) as character count grows.

Each scene follows: exposition -> complication -> climax -> resolution,
regardless of cast size. The arc determines who speaks when and what
narrative function each line serves.

Examples:
    >>> from app.schemas.dialog_arc import build_arc_from_moment, NarrativeShape
    >>> arc = build_arc_from_moment(moment_data)
    >>> arc.shape
    NarrativeShape.FREYTAG
    >>> len(arc.beats)
    7

Tests:
    - tests/unit/test_dialog_arc.py
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NarrativeShape(str, Enum):
    """Vonnegut's story shapes + Freytag's pyramid.

    Based on the Vermont computational study of 6,147 scripts that
    validated Vonnegut's classification of narrative arcs.
    """

    MAN_IN_HOLE = "man_in_hole"          # Good -> Bad -> Good (most common)
    CREATION = "creation"                  # Low -> Steady Rise (Apollo 11, Woodstock)
    CINDERELLA = "cinderella"              # Low -> High -> Low -> Very High
    FROM_BAD_TO_WORSE = "from_bad_to_worse"  # Bad -> Worse (Pompeii, Titanic)
    OLD_TESTAMENT = "old_testament"        # Rise -> Deep Fall (Icarus, Sarajevo)
    FREYTAG = "freytag"                    # Standard pyramid: exposition -> climax -> denouement


class NarrativeFunction(str, Enum):
    """What each dialog line does in the narrative arc."""

    ESTABLISH = "establish"      # Set scene, introduce status quo
    COMPLICATE = "complicate"    # Introduce tension/conflict
    ESCALATE = "escalate"        # Raise stakes
    TURN = "turn"                # Climactic moment / reversal
    REACT = "react"              # Response to the turn
    RESOLVE = "resolve"          # Resolution or new equilibrium
    PUNCTUATE = "punctuate"      # Final note / emotional coda


class ArcBeat(BaseModel):
    """One beat in the narrative arc, mapped to one dialog line.

    Attributes:
        position: Line index (0-6)
        narrative_function: What this line does narratively
        emotional_target: Target emotion (from MomentData.emotional_beats or default)
        speaker_role: Which type of speaker (primary/secondary/background)
        speaker_hint: Narrative hint for speaker selection
        intensity: Emotional intensity (0.0-1.0)
    """

    position: int = Field(ge=0, le=6)
    narrative_function: NarrativeFunction
    emotional_target: str = Field(default="neutral")
    speaker_role: str = Field(default="primary", description="primary/secondary/background")
    speaker_hint: str = Field(default="", description="Narrative hint for speaker selection")
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)


class DialogArc(BaseModel):
    """Full narrative arc for a 7-line dialog sequence.

    Attributes:
        shape: The Vonnegut/Freytag narrative shape
        beats: 7 arc beats, one per dialog line
        central_question: The dramatic question of the scene
        arc_summary: Brief description of the arc's trajectory
    """

    shape: NarrativeShape
    beats: list[ArcBeat] = Field(min_length=7, max_length=7)
    central_question: str = Field(default="")
    arc_summary: str = Field(default="")


# Intensity curves for each narrative shape (7 values, 0.0-1.0)
INTENSITY_CURVES: dict[NarrativeShape, list[float]] = {
    NarrativeShape.FREYTAG: [0.3, 0.4, 0.5, 0.7, 1.0, 0.6, 0.4],
    NarrativeShape.MAN_IN_HOLE: [0.6, 0.3, 0.2, 0.4, 0.7, 0.9, 0.7],
    NarrativeShape.CREATION: [0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0],
    NarrativeShape.CINDERELLA: [0.2, 0.6, 0.8, 0.3, 0.5, 0.9, 1.0],
    NarrativeShape.FROM_BAD_TO_WORSE: [0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 0.9],
    NarrativeShape.OLD_TESTAMENT: [0.3, 0.5, 0.8, 1.0, 0.7, 0.4, 0.2],
}

# Beat structure for each shape (narrative function per position)
BEAT_STRUCTURES: dict[NarrativeShape, list[NarrativeFunction]] = {
    NarrativeShape.FREYTAG: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.REACT,
        NarrativeFunction.RESOLVE,
    ],
    NarrativeShape.MAN_IN_HOLE: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.REACT,
        NarrativeFunction.RESOLVE,
        NarrativeFunction.PUNCTUATE,
    ],
    NarrativeShape.CREATION: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.PUNCTUATE,
    ],
    NarrativeShape.CINDERELLA: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.PUNCTUATE,
    ],
    NarrativeShape.FROM_BAD_TO_WORSE: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.REACT,
        NarrativeFunction.PUNCTUATE,
    ],
    NarrativeShape.OLD_TESTAMENT: [
        NarrativeFunction.ESTABLISH,
        NarrativeFunction.ESCALATE,
        NarrativeFunction.TURN,
        NarrativeFunction.REACT,
        NarrativeFunction.COMPLICATE,
        NarrativeFunction.RESOLVE,
        NarrativeFunction.PUNCTUATE,
    ],
}

# Speaker role mapping: which speaker type is best for each narrative function
FUNCTION_SPEAKER_ROLES: dict[NarrativeFunction, str] = {
    NarrativeFunction.ESTABLISH: "primary",
    NarrativeFunction.COMPLICATE: "secondary",
    NarrativeFunction.ESCALATE: "primary",
    NarrativeFunction.TURN: "primary",
    NarrativeFunction.REACT: "secondary",
    NarrativeFunction.RESOLVE: "primary",
    NarrativeFunction.PUNCTUATE: "background",
}

# Speaker hints for narrative guidance
FUNCTION_SPEAKER_HINTS: dict[NarrativeFunction, str] = {
    NarrativeFunction.ESTABLISH: "the one with most context to share",
    NarrativeFunction.COMPLICATE: "the one who introduces tension or disagrees",
    NarrativeFunction.ESCALATE: "the one with most at stake",
    NarrativeFunction.TURN: "the focal character — the pivotal voice",
    NarrativeFunction.REACT: "someone affected by what just happened",
    NarrativeFunction.RESOLVE: "the one who sees the way forward",
    NarrativeFunction.PUNCTUATE: "the outsider or observer — a final perspective",
}

# Default emotional targets when MomentData has no beats
DEFAULT_EMOTIONAL_BEATS: dict[NarrativeShape, list[str]] = {
    NarrativeShape.FREYTAG: [
        "anticipation", "tension", "urgency", "dread",
        "revelation", "shock", "acceptance",
    ],
    NarrativeShape.MAN_IN_HOLE: [
        "contentment", "worry", "despair", "determination",
        "effort", "relief", "gratitude",
    ],
    NarrativeShape.CREATION: [
        "curiosity", "wonder", "focus", "hope",
        "excitement", "triumph", "awe",
    ],
    NarrativeShape.CINDERELLA: [
        "longing", "hope", "joy", "loss",
        "determination", "triumph", "wonder",
    ],
    NarrativeShape.FROM_BAD_TO_WORSE: [
        "unease", "alarm", "fear", "dread",
        "horror", "despair", "resignation",
    ],
    NarrativeShape.OLD_TESTAMENT: [
        "pride", "ambition", "hubris", "shock",
        "regret", "sorrow", "acceptance",
    ],
}

# Mapping from MomentData tension_arc to narrative shape
TENSION_ARC_TO_SHAPE: dict[str, NarrativeShape] = {
    "climactic": NarrativeShape.FREYTAG,
    "rising": NarrativeShape.CREATION,
    "falling": NarrativeShape.OLD_TESTAMENT,
    "resolved": NarrativeShape.MAN_IN_HOLE,
}


def build_arc_from_moment(moment: object) -> DialogArc:
    """Build a DialogArc from MomentData.

    Maps MomentData fields to a narrative arc structure:
    - tension_arc -> narrative shape
    - emotional_beats -> beat emotional targets
    - stakes/central_question -> arc metadata

    Args:
        moment: MomentData instance

    Returns:
        DialogArc with 7 beats mapped to the narrative shape
    """
    # Determine shape from tension_arc
    tension_arc = getattr(moment, "tension_arc", "rising")
    shape = TENSION_ARC_TO_SHAPE.get(tension_arc, NarrativeShape.FREYTAG)

    # Get beat structure and intensity curve
    functions = BEAT_STRUCTURES[shape]
    intensities = INTENSITY_CURVES[shape]

    # Map emotional_beats from moment data, padding with defaults
    moment_beats = getattr(moment, "emotional_beats", None) or []
    default_beats = DEFAULT_EMOTIONAL_BEATS[shape]

    emotional_targets: list[str] = []
    for i in range(7):
        if i < len(moment_beats):
            emotional_targets.append(moment_beats[i])
        else:
            emotional_targets.append(default_beats[i])

    # Build beats
    beats: list[ArcBeat] = []
    for i in range(7):
        func = functions[i]
        beats.append(ArcBeat(
            position=i,
            narrative_function=func,
            emotional_target=emotional_targets[i],
            speaker_role=FUNCTION_SPEAKER_ROLES[func],
            speaker_hint=FUNCTION_SPEAKER_HINTS[func],
            intensity=intensities[i],
        ))

    # Extract arc metadata
    central_question = getattr(moment, "central_question", "") or ""
    stakes = getattr(moment, "stakes", "") or ""
    arc_summary = f"{shape.value}: {stakes}" if stakes else shape.value

    return DialogArc(
        shape=shape,
        beats=beats,
        central_question=central_question,
        arc_summary=arc_summary,
    )
