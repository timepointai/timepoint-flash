# PR-03 — Quick-sim grounding pass (opportunity liveness + temporal + Clockchain anchor)

**Layer-fit:** engine / breadth tier ↔ substrate · **Status: Not Started** ·
**Depends on:** PR-02 · **Effort:** M · **Cost/risk:** web/LLM-capped, medium.

> **Shared pattern with GSS / Clockchain — the grounding bridge.** GSS `PR-01a`
> anchors M20 grounding to the Clockchain DTI ("verified causal facts → synth
> knowledge"); this is Spine E (the grounding bridge) of the program map. The
> Flash breadth tier today **scores entirely ungrounded** — and a
> `probability_of_award` for an opportunity that has already closed, doesn't
> exist, or excludes the user is **fabricated confidence** in its purest form.
> This PR gives quick-sim a cheap, bounded grounding signal before it emits a
> number, the breadth-tier face of "ground before you score."

## Goal
Give the quick-sim path a **bounded grounding signal** so the metrics agent
scores against reality, not just the goal text. Quick-sim deliberately skips
Grounding + EntityGrounding (`app/core/pipeline.py::run_quick_sim`, L611) for
latency, and the `GroundingAgent` only fires on `QueryType.HISTORICAL`
(`app/agents/grounding.py::GroundingInput.needs_grounding`) — but quick-sim
renders a *future* moment, so grounding **never runs**. The result: scores
ignore whether the deadline has passed, whether the opportunity is real, or
whether the user is eligible. The current temporal grounding is only a date
string injected into the prompt (`app/prompts/temporal_grounding.py::
current_date_grounding`) — advisory, not enforced.

## Scope
**In:**
- A **lightweight, bounded grounding step** for the opportunity stub (not the
  full scene-grounding fan-out): a single capped check that establishes, where
  determinable, (a) **temporal liveness** — is the `deadline` in the past
  relative to `current_date_grounding()`? (deterministic, no LLM); (b)
  **existence/eligibility signal** — a single bounded grounding call (reusing
  the `GroundingAgent` machinery / Google-search grounding already in the repo)
  that returns whether the opportunity is corroborated and any hard
  eligibility/timing blocker.
- A **Clockchain anchor (optional, gated-cheap):** when the opportunity names a
  real organization/program that maps to a Clockchain figure/entity, attach the
  verified entity context as a grounding fact (Flash already constructs
  pipelines with `entity_ids` — `find_money.py::_build_generation_pipeline` —
  and has `app/agents/entity_grounding.py`). This is the Flash side of the
  GSS↔Clockchain grounding bridge; keep it **read-only** and **fail-open on
  Clockchain unavailability** (Flash must not hard-depend on the substrate).
- **Feed the grounding signal into scoring + confidence:** a past deadline is a
  **hard down-rank** (the prompt already says "a deadline in the past is a hard
  timing risk" — make it enforced, not advisory); a corroborated + eligible
  opportunity raises PR-02's `confidence_basis` from `inferred`→`grounded`; an
  ungroundable one caps it at `insufficient_evidence` (fail-closed).
- A **hard cost bound:** at most **one** extra grounding call per opportunity,
  inside the existing per-opp timeout + batch concurrency; the temporal check
  is free.

**Out:**
- Re-enabling the full scene Grounding/EntityGrounding fan-out on the quick-sim
  path (that is the latency sink quick-sim was built to avoid — keep it skipped;
  this is a *targeted* opportunity-grounding call, not the scene pipeline).
- Writing anything back to Clockchain (read-only here; the PORTAL→Clockchain
  contribution loop is GSS-side + gated).
- The calibration of how much grounding should move the score (**PR-01**
  measures that).

## Files / modules touched
- `app/api/v1/find_money.py` — `_simulate_one` (~L534–692): add the bounded
  opportunity-grounding step (temporal check + one grounding call) before the
  metrics agent; thread the grounding result into `scene_context` /
  metrics input and into PR-02's `confidence_basis`.
- `app/prompts/quick_sim.py` — `METRICS_USER_TEMPLATE` (~L152–183): replace the
  advisory "judge deadlines against this date" with an enforced
  grounding-fact block (`OPPORTUNITY GROUNDING: deadline_status=…,
  corroborated=…, blockers=[…]`); already imports `current_date_grounding`.
- `app/agents/grounding.py` — reuse `GroundingAgent` for a stub-level
  corroboration check; if `needs_grounding` gating is in the way, add a narrow
  `ground_opportunity_stub()` entry that doesn't require `HISTORICAL`.
- `app/agents/entity_grounding.py` — optional Clockchain entity anchor path
  (read-only, fail-open).

## Approach
1. **Free temporal check first.** Parse `deadline` vs. `current_date_grounding()`;
   a past deadline is a deterministic hard down-rank + risk — no LLM needed.
2. **One bounded grounding call.** Corroborate existence + surface a hard
   eligibility/timing blocker; cap to one call inside the per-opp timeout.
3. **Optional Clockchain anchor.** If the org maps to a verified entity, attach
   it as a grounding fact (read-only, fail-open — Flash never blocks on the
   substrate).
4. **Feed scoring + confidence.** Grounded+eligible → `grounded`; ungroundable
   → `insufficient_evidence` cap (fail-closed, via PR-02's machinery).
5. **Stay cheap.** The whole point of quick-sim is breadth; this adds at most
   one call/opportunity and a free date check.

## Acceptance criteria
- An opportunity with a past `deadline` is deterministically down-ranked and
  carries an explicit timing-risk flag (enforced, not just prompt-advisory).
- A corroborated, eligible opportunity reaches `confidence_basis == grounded`;
  an uncorroborated one is capped at `insufficient_evidence`.
- When a named org maps to a Clockchain entity, its verified context appears as
  a grounding fact; when Clockchain is unavailable, quick-sim still completes
  (fail-open, no hard dependency).
- At most one extra grounding LLM call per opportunity; the batch stays inside
  the existing per-opp timeout + concurrency bounds.

## Test plan (no mocks)
- `tests/unit`: the deterministic deadline-vs-today check (past/future/absent),
  pure.
- `tests/integration` (grounding/LLM HTTP boundary capped, Clockchain hit real
  or skipped): a stub with a past deadline → down-ranked + flagged; a
  corroborated stub → `grounded`; an unknown stub → `insufficient_evidence`.
- `tests/integration`: Clockchain unavailable → quick-sim still returns
  (fail-open) — assert no exception escapes.
- `pytest tests/unit tests/integration` green.

## Cost / safety
One bounded grounding call + a free temporal check per opportunity, inside
existing cost bounds. **Stability-key-neutral** (text/search grounding only, no
image). Clockchain read is fail-open. No deploy-private surface. Reversible —
the grounding step is additive and can be flagged off.

## Dependencies / merge order
**After PR-02** (grounding moves PR-02's `confidence_basis`). Feeds **PR-01**
(grounded scores are what the spine should show better-calibrated) and **PR-05**
(the handoff carries the grounding facts to Pro). The Clockchain-anchor half is
the Flash node of the program's **Spine E grounding bridge** (mirrors GSS
`PR-01a`).

## Status: Not Started
