# PR-02 — Fail-closed quick-sim scoring + per-metric confidence (no fabricated 0.5)

**Layer-fit:** engine / breadth tier · **Status: Not Started** ·
**Depends on:** none · **Effort:** M · **Cost/risk:** scoring-correctness, low.

> **Shared pattern with GSS / Clockchain:** this is the Flash face of GSS's
> "score honestly, fail closed" (GSS `PR-01b` removes RNG from scoring and
> excludes a candidate on a scoring error) and Clockchain's fail-closed
> promotion (never promote a `challenged` node). A breadth-tier score that
> can't be computed honestly must **exclude or down-rank with a flag**, never
> fabricate a mid-range number to fill the selection grid.

## Goal
Make every `QuickSimMetrics` value either **honestly grounded in the run** or
**explicitly flagged low-confidence / excluded** — never a fabricated
mid-range fill. Today the metrics agent
(`app/agents/quick_sim.py::QuickSimMetricsAgent`) returns a `QuickSimMetrics`
whose `probability_of_award` / `fit_score` / `effort_score` are taken at face
value with no confidence signal; on a metrics-agent failure `_simulate_one`
returns `success=False` (good — that path refunds + flags
`flash-quick-sim-error`), but there is **no middle path**: a metrics call that
*succeeds* but had nothing real to anchor on (e.g. an empty/garbage
`scene_context`, or an opportunity with no summary/amount/deadline) still emits
three confident-looking 0–1 floats. The prompt *asks* the model to "avoid
clustering at 0.5" but nothing enforces it.

## Scope
**In:**
- Add a **per-metric confidence** field to `QuickSimMetrics`: `score_confidence`
  (0–1) plus a `confidence_basis` enum (`grounded` / `inferred` /
  `insufficient_evidence`). The model self-reports it, *and* a deterministic
  post-check (below) can only **lower** it (fail-closed: the model cannot talk
  its way up past what the inputs support).
- **Deterministic confidence floor / cap** in a new pure
  `app/agents/quick_sim.py` helper (or `app/schemas/quick_sim.py` validator):
  if the opportunity stub is missing the fields a real assessment needs
  (no `summary` AND no `amount` AND no `deadline`), or the `scene_context` is
  the no-op fallback (`"(no scene context available)"` / `"(scene pipeline
  returned no usable summary)"` — both emitted by
  `find_money.py::summarize_tdf_for_metrics`), cap `score_confidence` at a low
  `insufficient_evidence` band and set `confidence_basis=insufficient_evidence`.
- **Down-rank, don't fabricate:** when `confidence_basis ==
  insufficient_evidence`, the entry is kept in the batch response (1:1 pairing
  is preserved) but flagged so the selection page can sort it below grounded
  entries — never silently mixed in at face value.
- Surface the new fields through `QuickSimTdfEntry` /
  `QuickSimBatchResponse` (`app/schemas/quick_sim.py`) so the web-app receives
  them; they are **additive + optional** so the existing
  `_seed_quick_sim_tdfs` pairing contract is unbroken.
- Tighten the prompt (`app/prompts/quick_sim.py::METRICS_SYSTEM_PROMPT`) to
  require the model to emit `score_confidence` + `confidence_basis` and to
  explicitly say "if you cannot ground a number, say so — an honest
  `insufficient_evidence` is worth more than a confident guess."

**Out:**
- The held-out calibration of *whether* the numbers are right (that is
  **PR-01**, the spine — this PR makes the score *honest about its own
  uncertainty*; PR-01 makes it *empirically calibrated*).
- Grounding the opportunity against the web / Clockchain (**PR-03**).
- The Flash→Pro contract changes (**PR-05**).

## Files / modules touched
- `app/schemas/quick_sim.py` — `QuickSimMetrics` (~L129–161): add
  `score_confidence: float = Field(ge=0, le=1)` and `confidence_basis: str`
  (enum); `QuickSimTdfEntry` (~L164–211) + `QuickSimBatchResponse`: thread the
  new fields (optional/defaulted).
- `app/prompts/quick_sim.py` — `METRICS_SYSTEM_PROMPT` (~L100–149) +
  `METRICS_USER_TEMPLATE` JSON schema block (~L174–183): add the two fields and
  the honesty instruction.
- `app/agents/quick_sim.py` — `QuickSimMetricsAgent.run` (~L100–109): after the
  LLM call, run the deterministic confidence post-check (pure helper) that can
  only *lower* `score_confidence`.
- `app/api/v1/find_money.py` — `_build_tdf_entry` (~L700–741): carry
  `score_confidence` / `confidence_basis` onto the entry; `_simulate_one`
  detects the no-op `scene_context` fallback and passes that signal in.

## Approach
1. **Add the fields, model-reported.** Extend the schema + prompt so the model
   emits a self-assessed confidence and basis alongside each number.
2. **Deterministic fail-closed floor.** A pure function inspects the *inputs*
   (opportunity stub completeness + whether `scene_context` is the no-op
   fallback) and **caps** confidence + forces `insufficient_evidence` — the
   model can never report higher confidence than the evidence supports.
3. **Down-rank, keep the row.** Preserve the 1:1 batch pairing; flag low-conf
   entries so the web-app sorts them below grounded ones. Never inject a 0.5.
4. **Additive contract.** New fields default so existing consumers
   (`_seed_quick_sim_tdfs`) are untouched.

## Acceptance criteria
- Every `QuickSimMetrics` carries `score_confidence` ∈ [0,1] and a
  `confidence_basis` ∈ {grounded, inferred, insufficient_evidence}.
- An opportunity stub with no summary/amount/deadline **and** a no-op
  `scene_context` produces `confidence_basis == insufficient_evidence` with a
  capped `score_confidence`, regardless of what the LLM self-reports.
- No code path emits a hard-coded mid-range fill score; the only ways out are
  (a) an honest grounded/inferred number with a confidence, or (b) a flagged
  `insufficient_evidence` row (or the pre-existing `flash-quick-sim-error`).
- New fields are optional/defaulted; existing `_seed_quick_sim_tdfs` pairing
  tests stay green.

## Test plan (no mocks)
- `tests/unit`: the deterministic confidence post-check — a complete stub +
  rich scene → confidence un-capped; an empty stub + no-op scene_context →
  `insufficient_evidence` cap (pure, no LLM).
- `tests/unit`: schema round-trips with the new fields; defaults preserve the
  old shape (assert a payload without the fields still parses).
- `tests/integration` (LLM HTTP boundary stubbed at the provider): a batch with
  one rich and one empty opportunity returns one grounded + one
  `insufficient_evidence` entry, both present, the empty one flagged.
- `pytest tests/unit tests/integration` green.

## Cost / safety
No new LLM calls (confidence is emitted in the same metrics call; the
post-check is pure). Stability-key-neutral (no image path). Reversible — fields
are additive; reverting drops them without breaking the pairing contract.
Lands entirely in the **open-source repo**; no deploy-private surface.

## Dependencies / merge order
**Root of the Flash spine** — no dependencies; build first. Feeds **PR-01**
(the spine calibrates the now-honest score), **PR-03** (grounding raises
confidence from `inferred`→`grounded`), **PR-05** (the handoff carries the
confidence), **PR-07** (CIs build on the confidence signal).

## Status: Not Started
