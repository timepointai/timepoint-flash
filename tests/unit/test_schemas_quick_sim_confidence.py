"""Unit tests for fail-closed quick-sim confidence (PR-02).

Covers the deterministic, pure post-check that keeps a no-signal quick-sim
score from emitting a confident-looking mid-range number:

    - ``opportunity_has_anchorable_fields`` — what counts as real signal.
    - ``scene_context_is_no_op`` — detecting the scene-pipeline fallbacks.
    - ``apply_confidence_floor`` — the fail-closed cap (only ever lowers).
    - schema round-trips: new fields are additive/optional (the old payload
      shape still parses), and ``QuickSimTdfEntry`` threads them through.

No LLM tokens are spent here — everything is pure logic / schema validation.
"""

from __future__ import annotations

import pytest

from app.schemas.quick_sim import (
    INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP,
    ConfidenceBasis,
    QuickSimMetrics,
    QuickSimTdfEntry,
    apply_confidence_floor,
    opportunity_has_anchorable_fields,
    scene_context_is_no_op,
)

NO_OP_SCENE = "(no scene context available)"
NO_OP_SCENE_2 = "(scene pipeline returned no usable summary)"


def _metrics(**overrides) -> QuickSimMetrics:
    base = {
        "probability_of_award": 0.2,
        "fit_score": 0.4,
        "effort_score": 0.5,
        "effort_estimate": "low — 4h application",
    }
    base.update(overrides)
    return QuickSimMetrics(**base)


# ---------------------------------------------------------------------------
# opportunity_has_anchorable_fields
# ---------------------------------------------------------------------------


def test_title_only_stub_has_no_anchorable_fields() -> None:
    assert opportunity_has_anchorable_fields({"title": "Climate Fund"}) is False


def test_empty_stub_has_no_anchorable_fields() -> None:
    assert opportunity_has_anchorable_fields({}) is False


@pytest.mark.parametrize(
    "stub",
    [
        {"title": "X", "summary": "Annual $10-50k grants for climate work"},
        {"title": "X", "amount": 50000},
        {"title": "X", "amount": "$25,000"},
        {"title": "X", "deadline": "2026-09-01"},
    ],
)
def test_any_real_field_makes_stub_anchorable(stub: dict) -> None:
    assert opportunity_has_anchorable_fields(stub) is True


def test_zero_amount_counts_as_present() -> None:
    # A numeric 0 amount is still a stated value, not a missing field.
    assert opportunity_has_anchorable_fields({"title": "X", "amount": 0}) is True


def test_blank_string_fields_do_not_count() -> None:
    assert (
        opportunity_has_anchorable_fields(
            {"title": "X", "summary": "   ", "deadline": "", "amount": None}
        )
        is False
    )


# ---------------------------------------------------------------------------
# scene_context_is_no_op
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scene", [NO_OP_SCENE, NO_OP_SCENE_2, "", None, "   "])
def test_no_op_scene_detection(scene) -> None:
    assert scene_context_is_no_op(scene) is True


def test_real_scene_is_not_no_op() -> None:
    assert scene_context_is_no_op("Setting: a tense boardroom; Stakes: $50k") is False


# ---------------------------------------------------------------------------
# apply_confidence_floor — fail-closed behaviour
# ---------------------------------------------------------------------------


def test_no_signal_path_caps_confidence_and_flags() -> None:
    """Empty stub + no-op scene -> insufficient_evidence, capped confidence.

    Regardless of how confident the model claimed to be.
    """
    m = _metrics(score_confidence=0.95, confidence_basis=ConfidenceBasis.GROUNDED)
    out = apply_confidence_floor(m, opportunity={"title": "Bare"}, scene_context=NO_OP_SCENE)
    assert out.confidence_basis == ConfidenceBasis.INSUFFICIENT_EVIDENCE
    assert out.score_confidence <= INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP


def test_no_signal_with_second_fallback_string() -> None:
    m = _metrics(score_confidence=0.8, confidence_basis=ConfidenceBasis.INFERRED)
    out = apply_confidence_floor(m, opportunity={}, scene_context=NO_OP_SCENE_2)
    assert out.confidence_basis == ConfidenceBasis.INSUFFICIENT_EVIDENCE
    assert out.score_confidence <= INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP


def test_floor_only_lowers_never_raises_confidence() -> None:
    """An already-low self-report is not bumped UP by the cap."""
    m = _metrics(score_confidence=0.02, confidence_basis=ConfidenceBasis.INSUFFICIENT_EVIDENCE)
    out = apply_confidence_floor(m, opportunity={}, scene_context=NO_OP_SCENE)
    assert out.score_confidence == pytest.approx(0.02)
    assert out.confidence_basis == ConfidenceBasis.INSUFFICIENT_EVIDENCE


def test_valid_path_leaves_confidence_untouched() -> None:
    """Rich stub + real scene -> model's grounded self-report is preserved."""
    m = _metrics(score_confidence=0.82, confidence_basis=ConfidenceBasis.GROUNDED)
    rich = {
        "title": "Climate Action Fund",
        "summary": "Annual $10-50k grants for climate work",
        "amount": 50000,
        "deadline": "2026-09-01",
    }
    out = apply_confidence_floor(
        m, opportunity=rich, scene_context="Setting: boardroom; Stakes: $50k on the line"
    )
    assert out.score_confidence == pytest.approx(0.82)
    assert out.confidence_basis == ConfidenceBasis.GROUNDED
    # Pure: no mutation of the input object.
    assert m.confidence_basis == ConfidenceBasis.GROUNDED


def test_grounded_claim_downgraded_when_scene_missing_but_stub_has_signal() -> None:
    """A 'grounded' claim cannot stand without a usable scene.

    The opportunity stub still carries signal (so NOT insufficient_evidence),
    but the basis is downgraded grounded -> inferred.
    """
    m = _metrics(score_confidence=0.7, confidence_basis=ConfidenceBasis.GROUNDED)
    out = apply_confidence_floor(
        m, opportunity={"title": "X", "amount": 50000}, scene_context=NO_OP_SCENE
    )
    assert out.confidence_basis == ConfidenceBasis.INFERRED
    # Confidence is not raised; left as the (still un-capped) self-report.
    assert out.score_confidence == pytest.approx(0.7)


def test_no_signal_never_emits_fabricated_midrange() -> None:
    """The fail-closed cap is well below the 0.5 'fabricated mid-range' band."""
    assert INSUFFICIENT_EVIDENCE_CONFIDENCE_CAP < 0.5


# ---------------------------------------------------------------------------
# schema round-trips — additive / optional contract
# ---------------------------------------------------------------------------


def test_metrics_payload_without_new_fields_still_parses() -> None:
    """Old shape (no score_confidence / confidence_basis) parses with defaults."""
    m = QuickSimMetrics(
        probability_of_award=0.3,
        fit_score=0.4,
        effort_score=0.6,
        effort_estimate="moderate — 20h proposal",
    )
    assert 0.0 <= m.score_confidence <= 1.0
    assert m.confidence_basis in set(ConfidenceBasis)


def test_metrics_round_trip_with_new_fields() -> None:
    m = _metrics(score_confidence=0.66, confidence_basis=ConfidenceBasis.INFERRED)
    dumped = m.model_dump()
    assert dumped["score_confidence"] == pytest.approx(0.66)
    assert dumped["confidence_basis"] == "inferred"
    reloaded = QuickSimMetrics.model_validate(dumped)
    assert reloaded.confidence_basis == ConfidenceBasis.INFERRED


def test_confidence_basis_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        QuickSimMetrics(
            probability_of_award=0.3,
            fit_score=0.4,
            effort_score=0.6,
            effort_estimate="x",
            confidence_basis="totally_made_up",
        )


def test_score_confidence_out_of_band_rejected() -> None:
    with pytest.raises(ValueError):
        QuickSimMetrics(
            probability_of_award=0.3,
            fit_score=0.4,
            effort_score=0.6,
            effort_estimate="x",
            score_confidence=1.5,
        )


def test_tdf_entry_threads_confidence_fields() -> None:
    entry = QuickSimTdfEntry(
        tdf_ref="flash:quick:0",
        opportunity_index=0,
        title="Climate Fund",
        source="flash-quick-sim",
        score_confidence=0.1,
        confidence_basis=ConfidenceBasis.INSUFFICIENT_EVIDENCE,
    )
    assert entry.confidence_basis == ConfidenceBasis.INSUFFICIENT_EVIDENCE
    assert entry.score_confidence == pytest.approx(0.1)


def test_tdf_entry_without_confidence_fields_still_parses() -> None:
    """Existing _seed_quick_sim_tdfs pairing contract is unbroken."""
    entry = QuickSimTdfEntry(
        tdf_ref="flash:quick:1",
        opportunity_index=1,
        title="X",
        source="flash-quick-sim-error",
    )
    assert entry.score_confidence is None
    assert entry.confidence_basis is None
