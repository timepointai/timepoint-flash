# PR-01 — Quick-sim calibration spine (held-out ground truth) — KEYSTONE

**Layer-fit:** engine / breadth tier · **Status: Not Started**
(**cross-repo** into `timepoint-snag-bench`) · **Depends on:** PR-02 ·
**Effort:** L · **Cost/risk:** eval LLM-capped, cross-repo, medium.

> **Shared pattern with GSS / Clockchain — this is the SAME spine.** GSS
> `PR-02` ("Calibration spine, KEYSTONE") elevates SNAG-bench to the held-out,
> human-labeled ground-truth that every GSS threshold anchors to
> (Spearman / Brier / separability). Clockchain `PR-02a` requires proposer
> reputation to *empirically* predict a lower later-challenge rate or the band
> is wrong. **Flash's quick-sim scores must join the same spine.** Until a
> Flash `probability_of_award` is calibrated against real outcomes, it is "a
> guess wearing a number" — and because the web-app surfaces it directly to the
> user when Pro is skipped (`_quick_sim_derived_results`), it is an
> *unfalsifiable product claim*. This is the keystone: nothing else in the
> Flash queue is falsifiable without it.

## Goal
Stand up a **held-out, outcome-labeled evaluation set** for quick-sim scores
and wire Flash to it so a `probability_of_award` / `fit_score` / `effort_score`
can be measured for **calibration** (do predicted probabilities match observed
frequencies — Brier / reliability curve) and **separability** (do better
opportunities actually score higher — Spearman / rank correlation against
labeled outcomes). Replace the latency-only eval (`app/eval/`, whose roadmap
admits "**Gap: Measures speed only, not quality**") with a quality spine that
shares SNAG-bench's discipline.

## Scope
**In:**
- A held-out **quick-sim eval set**: (goal, opportunity stub, label) triples
  where the label is a real or expert-judged outcome (won/lost, good-fit/
  bad-fit, light/heavy effort). Sourced from real Find-Money runs where the
  outcome is known + a curated seed set. Lives in `timepoint-snag-bench`
  alongside the existing SNAG harness so the **same eval infra scores both
  tiers** (Flash breadth + Pro depth) on the same scale.
- A **calibration scorer**: given Flash's predicted `probability_of_award`
  across the eval set and the binary outcomes, compute **Brier score** +
  **reliability curve** (predicted-vs-observed by bucket); given `fit_score` /
  `effort_score` vs. labels, compute **Spearman rank correlation** +
  **separability** (does the top-quartile-by-score have a materially higher
  win rate than the bottom quartile?).
- A **calibration report** artifact + a CI gate: the spine runs the quick-sim
  batch endpoint (real Flash, LLM boundary capped) over the eval set and emits
  the metrics; a regression (Brier worse than baseline, Spearman collapses)
  **fails loud**.
- Anchor PR-02's confidence bands to this spine: an `insufficient_evidence`
  flag should empirically correlate with a worse Brier (the model knows when
  it doesn't know) — if it doesn't, the band is mis-set.

**Out:**
- The fail-closed scoring mechanics (**PR-02**, prerequisite).
- Re-training any model on the eval (that is the LOOP-layer RLSF work, **gated**
  — same gate as GSS `PR-03`; do not build the training loop here).
- The Pro-side calibration (lives in GSS `PR-02`; this spec makes Flash a
  *first-class citizen of the same spine*, not a separate one).

## Files / modules touched
- **`timepoint-snag-bench` (cross-repo):** add a `quick_sim/` eval set + a
  calibration scorer module reusing the existing SNAG harness structure (mirror
  GSS `PR-02`'s cross-repo landing). The Flash batch endpoint
  (`POST /api/v1/find-money/quick-sim-batch`) is the system-under-test.
- **`timepoint-flash` (engine):**
  - `app/eval/runner.py` + `app/eval/schemas.py` — extend beyond latency: add a
    `quality`/`calibration` eval mode that records predicted scores + (when
    available) labels, so the spine can read Flash output in a stable shape.
  - `docs/EVAL_ROADMAP.md` — update the "Gap: speed only" note: the quality gap
    is now addressed by the calibration spine.

## Approach
1. **Build the labeled set** (cross-repo, snag-bench): real Find-Money outcomes
   where known + a curated seed; store (goal, stub, label) with provenance.
2. **Score calibration, not latency:** Brier + reliability for
   `probability_of_award`; Spearman + quartile-separability for
   `fit_score`/`effort_score`. RNG-free, deterministic given the recorded
   outputs.
3. **Run real Flash over the set** with the LLM provider boundary capped; record
   predictions through the extended `app/eval` runner.
4. **Gate on regression** and **cross-check PR-02's bands:** verify the
   `insufficient_evidence` flag predicts worse Brier; narrow the band if not
   (exactly Clockchain `PR-02a`'s "calibrate the band before trusting it").
5. **One scale for both tiers:** keep the scorer identical to the GSS/Pro side
   so a Flash score and a Pro score are measured the same way — the
   precondition for PR-05's calibrated handoff.

## Acceptance criteria
- A held-out quick-sim eval set with outcome labels + provenance exists in
  `timepoint-snag-bench`.
- Running the spine over real Flash output yields a Brier score + reliability
  curve for `probability_of_award` and a Spearman + quartile-separability
  number for `fit_score`/`effort_score`.
- A scoring-quality regression fails the spine loudly (not silently).
- The PR-02 `insufficient_evidence` flag is shown to predict a worse Brier
  (else the band is reported as mis-calibrated and narrowed).
- The scorer is shared with / identical to the GSS/Pro calibration scorer
  (same scale across breadth + depth tiers).

## Test plan (no mocks)
- `timepoint-snag-bench` `tests/`: the calibration scorer on a synthetic
  labeled set with known Brier/Spearman (pure math, asserted to closed form).
- `timepoint-flash` `tests/integration`: the extended eval runner records
  predicted scores in the calibration shape over a small real batch (provider
  HTTP capped); no mocks of the pipeline.
- End-to-end smoke: run the spine over a tiny labeled fixture and assert the
  report contains Brier + Spearman + separability.

## Cost / safety
The eval LLM cost is the quick-sim batch over the eval set — **capped**: small
held-out set, batch concurrency + per-opp timeout already bound it
(`find_money.py`), runs in CI/offline not per-user. Stability-key-neutral.
**Cross-repo:** the snag-bench branch is pushed but the director opens that PR
manually (`feedback_cross_repo_pr_opening`). No deploy-private surface in Flash;
the snag-bench harness is its own repo.

## Dependencies / merge order
**After PR-02** (the spine calibrates an *honest* score; calibrating a
fabricated 0.5 is meaningless). **The keystone** — PR-05 (calibrated handoff)
and PR-06 (drift canary) both anchor to the scale this establishes. Joins the
**same spine** as GSS `PR-02`; coordinate the shared scorer.

## Status: Not Started
