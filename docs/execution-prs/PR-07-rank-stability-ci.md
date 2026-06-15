# PR-07 — Rank-stability + ties: surface CIs so a "tied" shortlist reads as tied

**Layer-fit:** engine / breadth tier · **Status: Not Started** ·
**Depends on:** PR-02 · **Effort:** S · **Cost/risk:** scoring-presentation, low.

> **Shared pattern with GSS.** GSS `PR-01b` attaches a **confidence interval**
> to every `outcome_score` (`outcome_score_low`/`outcome_score_high`) "so
> consumers see when two leads are statistically tied." The Flash breadth tier
> ranks up to 15 opportunities and the user shortlists the top-N for expensive
> Pro deep-sim — if opportunities #5 and #6 are statistically indistinguishable,
> presenting a hard rank that puts #6 below the cut is **fabricated precision**.
> Same idea, breadth-tier face: a tie must read as a tie.

## Goal
Surface a confidence band on each quick-sim score so the selection page can show
when two opportunities are **statistically tied** rather than implying a false
ordering, and so the breadth→depth handoff (PR-05) carries the band. Builds
directly on PR-02's `score_confidence` (the band width follows from the
confidence + basis).

## Scope
**In:**
- Derive a **confidence band** per scored metric from PR-02's `score_confidence`
  + `confidence_basis`: a low-confidence / `inferred` score gets a wide band, a
  `grounded` high-confidence score a narrow one. Deterministic mapping (no RNG),
  or — where the `depth` tier runs multiple samples — a real spread.
- Add `probability_low`/`probability_high` (and the same for `fit_score`) to
  `QuickSimMetrics` / `QuickSimTdfEntry` (`app/schemas/quick_sim.py`), additive
  + optional (preserves the `_seed_quick_sim_tdfs` pairing).
- A **tie helper** (pure): two opportunities whose bands overlap beyond a
  threshold are flagged `rank_tied` so the web-app can present them as a tied
  cluster rather than a hard 1-2-3 order.

**Out:**
- The held-out calibration of the band widths (**PR-01** measures whether a
  "narrow" band is actually narrow); this PR *surfaces* uncertainty, PR-01
  *validates* it.
- Web-app rendering of the tie cluster (web-app's job; this PR provides the
  `rank_tied` signal).

## Files / modules touched
- `app/schemas/quick_sim.py` — `QuickSimMetrics` (~L129–161) +
  `QuickSimTdfEntry` (~L164–211): add `probability_low/high`, `fit_score_low/high`
  (optional/defaulted); a `rank_tied` flag on the entry.
- `app/agents/quick_sim.py` or a new pure helper: confidence → band mapping.
- `app/api/v1/find_money.py` — `_run_batch` / `_build_tdf_entry`
  (~L817–741): compute `rank_tied` across the batch's entries (pure, after all
  settle) so overlapping bands are flagged.

## Approach
1. **Band from confidence.** Map PR-02's `score_confidence`/`confidence_basis`
   to a deterministic band width (wider for `inferred`/low-conf).
2. **Flag ties.** A pure cross-batch pass marks entries whose bands overlap
   beyond threshold as `rank_tied`.
3. **Carry it.** The band + tie flag ride on the entry into PR-05's handoff and
   PR-06's recorder.

## Acceptance criteria
- Each scored metric carries a `_low`/`_high` band; a `grounded` high-confidence
  score has a narrower band than an `inferred` low-confidence one.
- Two opportunities with overlapping bands are flagged `rank_tied`; clearly
  separated ones are not.
- Fields are additive/optional; `_seed_quick_sim_tdfs` pairing tests stay green.
- No RNG in the band derivation (deterministic from confidence).

## Test plan (no mocks)
- `tests/unit`: confidence→band mapping (high-conf narrow, low-conf wide), pure.
- `tests/unit`: the tie helper — overlapping bands → `rank_tied`, separated → not.
- `tests/integration` (LLM boundary capped): a batch with two near-identical
  opportunities returns them `rank_tied`; a clearly-better one is not tied with
  a clearly-worse one.
- `pytest tests/unit tests/integration` green.

## Cost / safety
No new LLM cost (band derives from existing confidence; the helper is pure).
Stability-key-neutral. Additive/reversible. Open-source repo only.

## Dependencies / merge order
**After PR-02** (the band derives from PR-02's confidence). Feeds **PR-05** (the
handoff carries the band + tie flag) and **PR-06** (the recorder logs it).
Mirrors GSS `PR-01b`'s CI work.

## Status: Not Started
