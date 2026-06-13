# PR-06 — Quick-sim observability: score flight-recorder + calibration-drift canary

**Layer-fit:** engine / breadth tier (cross-cutting) · **Status: Not Started** ·
**Depends on:** PR-01 · **Effort:** M · **Cost/risk:** observability only, low.

> **Shared pattern with GSS / Clockchain.** GSS `PR-XX-obs` adds full mechanism
> tracking + a run flight-recorder; Clockchain `PR-XX` adds a data canary. The
> Flash face is a **score flight-recorder + calibration-drift canary**: a
> calibrated breadth-tier score (PR-01) is only trustworthy if you can *see* it
> drift. This guards every later run the same way the GSS/Clockchain canaries do
> — and the ecosystem alarm is **CI/canary red, not Slack** (`feedback_no_slack`).

## Goal
Record, per quick-sim run, the inputs and outputs needed to (a) reproduce a
score and (b) detect **calibration drift** over time, and stand up a canary that
fails loud when the live score distribution diverges from the PR-01 spine's
calibrated baseline — e.g. probabilities start clustering at 0.5 again, the
`insufficient_evidence` rate spikes (grounding broke), or a slug silently
degraded (catches the PR-04 failure mode in production).

## Scope
**In:**
- A **score flight-recorder**: structured log/record per opportunity capturing
  goal, opportunity stub digest, resolved `depth`/model slug, the five metrics +
  `score_confidence` + `confidence_basis` (PR-02), grounding result (PR-03),
  `calibration_ref` (PR-01), and latency. Enough to reproduce + audit a score.
  Flash already logs richly in `find_money.py` (`logger.info` per opportunity);
  this is a structured, queryable record, not free-text.
- A **calibration-drift canary** (cross-repo ops, mirrors the ecosystem
  cron/canary pattern): periodically score a small fixed probe set through the
  live quick-sim endpoint and compare the distribution + Brier against the PR-01
  baseline; **fail loud** (red CI/cron) on drift — clustering, confidence
  collapse, or a Brier regression.
- Surface aggregate health (score distribution, `insufficient_evidence` rate,
  mean confidence) read-only, so a human can see the breadth tier's honesty at
  a glance.

**Out:**
- Re-training / auto-correction (LOOP-layer RLSF, **gated** — same gate as GSS
  `PR-03`).
- Per-user PII in the recorder (record a stub *digest*, respect key-hygiene).
- The calibration math itself (**PR-01**).

## Files / modules touched
- `app/api/v1/find_money.py` — `_simulate_one` / `_build_tdf_entry`
  (~L534–741): emit the structured score record alongside the existing
  `logger.info` calls.
- `app/eval/runner.py` — reuse the PR-01 calibration scorer for the canary's
  baseline comparison (the canary is the spine run on a fixed probe set on a
  schedule).
- **Cross-repo ops** (`timepoint-dev-management` cron / canary infra, mirrors
  `uptime-monitor.py` / `db-health-check.py`): a scheduled quick-sim calibration
  probe that fails loud on drift.

## Approach
1. **Record what reproduces a score.** Structured per-opportunity record
   (inputs digest + outputs + confidence + grounding + slug + calibration_ref).
2. **Probe + compare on a schedule.** Run a fixed probe set through the live
   endpoint; compare distribution + Brier to the PR-01 baseline.
3. **Fail loud.** Drift → red canary (the alarm), never a silent degrade —
   catches re-clustering, confidence collapse, broken grounding, and dead slugs
   in production.

## Acceptance criteria
- Every quick-sim opportunity emits a structured, reproducible score record
  (no raw PII — stub digest only).
- A scheduled canary scores a fixed probe set and compares to the PR-01
  baseline; a drift (clustering, `insufficient_evidence` spike, Brier
  regression) fails the canary loud.
- Aggregate breadth-tier health (distribution, conf, insufficient rate) is
  readable.

## Test plan (no mocks)
- `tests/unit`: the score-record builder produces the full reproducible record
  from a `_simulate_one` result; asserts no raw PII (digest only).
- `tests/integration`: a probe batch run through the real endpoint (LLM
  boundary capped) yields records the canary can score against the PR-01
  baseline; an injected clustering distribution trips the drift check.
- Canary cron tested against a fixture baseline (drift vs. no-drift cases).

## Cost / safety
Recorder is logging-only (no LLM). The canary cost is one small probe batch on a
schedule — capped, off the user path. Stability-key-neutral. Respects
key-hygiene (digest, no PII). No deploy-private surface in Flash; the canary is
ops cron in dev-management. Reversible.

## Dependencies / merge order
**After PR-01** (the canary needs the calibrated baseline to drift *from*).
Cross-cutting — guards PR-03 (grounding break shows as confidence collapse),
PR-04 (a dead slug shows as a distribution shift), and PR-05 (a handoff scale
regression shows as Brier drift). Mirrors GSS `PR-XX-obs` + Clockchain
`PR-XX-data-canary`.

## Status: Not Started
