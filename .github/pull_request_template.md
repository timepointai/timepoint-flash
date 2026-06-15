<!-- Flash execution-PR template. See docs/execution-prs/README.md. -->

## What & why
<!-- Link the PR-*.md spec. One paragraph: what this lands and why now. -->

Implements: `docs/execution-prs/PR-__.md`

## Flash breadth-tier safety checklist

Every quick-sim scoring change obeys the guiding constraints
(`docs/execution-prs/README.md`). Tick or N/A each:

- [ ] **Comparable, not ad-hoc** — the score means the same on the same scale
      (anchored to the PR-01 calibration spine); two scores are honestly rankable.
- [ ] **Fail closed** — a scoring error / ungroundable / low-confidence input
      excludes or down-ranks with an honest flag; **no fabricated mid-range 0.5**.
- [ ] **Grounded before scored** — temporal liveness + (where determinable)
      corroboration/eligibility feed the score; ungroundable → `insufficient_evidence`.
- [ ] **Slug-validated** — the resolved `depth`/frontier model slug is
      liveness-checked; a dead slug fails loud, never emits garbage scores.
- [ ] **Cost-capped** — per-opportunity timeout + batch concurrency + per-opp
      credit bounds preserved; no unbounded fan-out.
- [ ] **Charge on success only** — failed opportunities refunded; the
      `X-Gateway-Metered` contract is respected (no double-charge).
- [ ] **Stability-key-neutral** — no new inline image render on the quick-sim
      path; Stability-key isolation preserved.
- [ ] **Deploy-private noted** — any billing / blob-storage surface that lands
      in `timepoint-flash-deploy-private-feb-2026` is called out (sync is
      surgical cherry-pick, not merge).
- [ ] **Calibration-aware** — if this changes scoring, the impact on the PR-01
      spine (Brier / Spearman / separability) is stated.

## Tests (no mocks)
<!-- Per repo policy, only the LLM/provider HTTP boundary may be stubbed.
     List the tests/unit, tests/integration, tests/e2e you added. -->

- [ ] `pytest tests/unit tests/integration` green
- [ ] No mocks beyond the LLM/provider HTTP boundary

## Reversibility
<!-- How to revert. Additive/optional schema fields preferred. -->
