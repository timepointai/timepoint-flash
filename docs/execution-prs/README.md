# Flash — Engine-Integration Execution PR Tracker

This directory positions **Timepoint Flash** inside the unified
**grounded world-model loop** (mapped in
`timepoint-dev-management/docs/TIMEPOINT_PROGRAM.md`,
branch `docs-timepoint-program-jun13`) and turns that positioning into
**ready-to-implement PR specs**. Each `PR-*.md` is a self-contained brief an
agent can pick up and execute without re-deriving the design.

These are **specs, not code.** Nothing here implements a feature or deploys.
Already-shipped work is documented at its *real* status, not re-specced.

> This tracker **mirrors exactly** the house style established by the GSS
> queue (`timepoint-pro-internal/docs/execution-prs/`) and the Clockchain
> queue (`timepoint-clockchain/docs/execution-prs/`): index README with
> guiding constraints + PR-index table + merge-order DAG, one self-contained
> `PR-*.md` spec per work item, plus `.github` PR + issue templates. The same
> format lets a team of agents iterate over **all three engine/substrate
> queues** identically.

## Where Flash sits in the architecture

The program is one loop: **SUBSTRATE** (Clockchain causal graph + entity
registry) → **ENGINE** (simulation) → **LOOP** (TDF export → SNAG-bench →
gated training) → **PRODUCT** (web-app + skipmeetings).

**Flash is the breadth tier of the ENGINE layer.** GSS / Timepoint Pro is the
depth tier (deep-sim + PORTAL abduction). They are **not two engines** — they
are the two halves of **one simulation engine**:

- **Flash = quick-sim / breadth.** Given a goal and 1–15 opportunity stubs, it
  renders a fast future-moment TDF per opportunity (the LIGHT pipeline path:
  Judge → Timeline → Scene → CharacterID → Moment, five LLM calls —
  `app/core/pipeline.py::run_quick_sim`) and extracts five structured fit
  metrics (`probability_of_award`, `fit_score`, `effort_score`, risks, levers
  — `app/agents/quick_sim.py`, `app/schemas/quick_sim.py`). It is the
  **first-pass ranker** in the Find-Money pipeline: web-search sourcing →
  **Flash quick-sim batch** → user selects top-N → Pro deep-sim (optional) →
  result.
- **GSS/Pro = deep-sim / depth.** It re-simulates the selected opportunities
  with the 21-mechanism engine, forward/branching/abductive.

**The breadth tier's job is to spend the depth tier's budget wisely.** A
Flash quick-sim score that is not comparable, not calibrated, and not grounded
sends the user's expensive Pro deep-sim spend at noise — and, when the user
skips Pro, **Flash's `probability_of_award` is surfaced to the user as the
final answer** (web-app `_quick_sim_derived_results` in
`app/find_money/runs/jobs.py`). So Flash scores are *product output*, not just
an internal pre-filter.

### The one discipline (shared across every queue)

**Grounded confidence over fabricated confidence.** No number is trusted until
it has been calibrated against ground truth or corroborated. Fail closed.
Score honestly. Reversible + audited. Hard cost bounds. Respect the synths.

Today, Flash's scoring discipline is **prompt-only**. The metrics system prompt
(`app/prompts/quick_sim.py::METRICS_SYSTEM_PROMPT`) *asks* the model to "anchor
against base rates", "avoid clustering at 0.5", and "calibrate" — but there is:

- **no held-out ground truth** (the only eval, `app/eval/`, measures *latency*,
  not accuracy — `docs/EVAL_ROADMAP.md` says so explicitly: "**Gap: Measures
  speed only, not quality**");
- **no comparability guarantee** between two Flash scores or between a Flash
  score and a Pro score (the Flash→Pro handoff carries raw 0–1 floats with no
  shared scale — web-app `jobs.py`);
- **no grounding** on the quick-sim path at all (`run_quick_sim` *deliberately
  skips* Grounding + EntityGrounding — `pipeline.py` L611 — and the
  `GroundingAgent` only fires on `QueryType.HISTORICAL`, while quick-sim renders
  a *future* moment, so it would never fire anyway);
- **no fail-closed scoring** — a metrics-agent value is taken at face value;
  there is no exclusion-on-low-confidence path, and `np`-style RNG is absent
  but the temperature-0.3 LLM is the only thing standing between two
  opportunities and an identical 0.5.

This is the **same pathology** the GSS Math-Integrity review found ("uncalibrated
thresholds, no ground-truth calibration wired up, no score is falsifiable") —
in a different repo. The integration plan below aligns Flash's quick-sim
scoring to the **same calibration spine + fail-closed + grounded-confidence
discipline** as GSS/Clockchain, and defines the **Flash→Pro handoff as a
first-class, calibrated contract**.

## Vendored deploy / Stability realities (do not break these)

- **Open-source upstream + private deploy fork.** This repo is the *upstream
  reference implementation* (ships `NoOpBilling` + `local` blob backend). The
  live `flash.timepointai.com` service runs from the **private fork**
  `timepoint-flash-deploy-private-feb-2026`, which adds billing, R2 blob
  storage, and request-signing (`docs/DEPLOY.md`, `docs/STORAGE.md`). Every
  spec here is authored against the **open-source paths**; anything touching
  billing or blob storage must call out the deploy-private surface it lands in.
  Per `feedback_deploy_private_sync`, deploy-private sync is **surgical
  `git cherry-pick`, not merge**.
- **Auth is stripped here, owned by the gateway.** `AUTH_ENABLED=false`
  (`app/config.py` L514); Flash sits behind `timepoint-api-gateway`, which owns
  user auth + credits and sets `X-Gateway-Metered` to prevent double-charging
  (`find_money.py::_maybe_spend_credits`). Specs must respect the gateway
  metering contract — never re-introduce a charge the gateway already metered.
- **Stability key isolation.** Flash is the **only** service that holds a
  Stability image key (`VerifiedModels.STABILITY_IMAGE`); Clockchain's image
  renders were a documented drain on it and were isolated/turned off
  (`reference_stability_key_routing.md`). The quick-sim path **does not render
  images** inline (`generate_image` is ignored; images are a fire-and-forget
  background task — `find_money.py::_schedule_quick_sim_image_gen`), so the
  scoring work here is **Stability-key-neutral**. Any spec that touches image
  cost must preserve that isolation.

## The guiding constraints (every PR obeys these)

Learned, non-negotiable (mirrors the GSS/Clockchain constraints, specialised to
the breadth tier):

- **A quick-sim score must be comparable, not ad-hoc.** Two Flash scores —
  and a Flash score vs. a Pro score — must mean the same thing on the same
  scale, or the ranking is noise and the handoff lies. Calibration before
  trust. *(Shared pattern with GSS `PR-02` calibration spine + Clockchain
  proposer-reputation calibration.)*
- **Ground before you score.** A `probability_of_award` for an opportunity
  whose deadline has passed, whose eligibility excludes the user, or that
  doesn't exist, is fabricated confidence. Quick-sim must have *some* grounding
  signal — at minimum a cheap, bounded liveness/temporal check — before it
  emits a number. *(Shared pattern with GSS `PR-01a` Clockchain-DTI anchor +
  Clockchain corroboration.)*
- **Fail closed.** A metrics-agent error, an ungroundable opportunity, or a
  low-confidence read must **exclude or down-rank with an honest flag** — never
  fabricate a mid-range 0.5 to fill the grid. *(Shared with GSS "score
  honestly, fail closed".)*
- **Pin and guard model slugs.** `VerifiedModels` is a **static hardcoded
  list** (`config.py` L88–139, incl. `anthropic/claude-opus-4.8` for the
  `frontier` depth tier) with **no liveness check** — a silently-deprecated
  OpenRouter slug 404s and the batch returns empty/garbled scores. The resolver
  must validate the resolved slug is live and **fail loud**. *(Shared pattern
  with GSS `PR-00c` slug-liveness guard — this is the **same guard**, same
  failure mode, documented in `reference_dead_model_slug_failure_mode.md`.)*
- **Hard cost bounds, always.** Quick-sim batches up to 15 opportunities × the
  five-call light path × a per-opportunity credit; the batch must stay cheap
  enough that users run discovery before paying for Pro. Concurrency + per-opp
  timeout + per-opp credit are bounded today (`find_money.py`); keep them so.
  *(Shared with GSS `budget_limit_usd` / `HARD_CONSTRAINT`.)*
- **Charge on success only.** Already honored — failed opportunities are
  refunded (`find_money.py::_refund_credits`); the gateway-metered header
  short-circuits per-opp charges. Mirrors GSS `PR-00d` charge-on-success.

## PR index

Status legend: `Not Started` · `In Progress` · `In Review` · `Done` ·
`Gated` (do not build yet).

| ID | Title | Layer-fit | Status | Depends on | Effort | Cost / risk |
|----|-------|-----------|--------|------------|--------|-------------|
| [PR-01](PR-01-quick-sim-calibration-spine.md) | **Quick-sim calibration spine (held-out ground truth, KEYSTONE)** | engine/breadth | Not Started (**cross-repo** `timepoint-snag-bench`) | PR-02 | L | eval LLM-capped, **cross-repo**, medium |
| [PR-02](PR-02-fail-closed-confidence-scoring.md) | Fail-closed scoring + per-metric confidence (no fabricated 0.5) | engine/breadth | Not Started | none | M | scoring-correctness, low |
| [PR-03](PR-03-quick-sim-grounding-pass.md) | Quick-sim grounding pass (opportunity liveness + temporal + Clockchain anchor) | engine/breadth ↔ substrate | Not Started | PR-02 | M | web/LLM-capped, medium |
| [PR-04](PR-04-model-slug-liveness-guard.md) | Model-slug liveness guard (fail loud on dead `depth`/frontier slugs) | engine/breadth (guard) | Not Started | none | S | 1 catalog call/run, low |
| [PR-05](PR-05-flash-to-pro-calibrated-handoff.md) | **Flash→Pro calibrated handoff contract (breadth-rank → depth-select)** | engine (breadth↔depth seam) | Not Started | PR-01, PR-02 | M | cross-repo contract (web-app + pro-cloud), medium |
| [PR-06](PR-06-quick-sim-observability.md) | Quick-sim observability — score flight-recorder + calibration drift canary | engine/breadth (cross-cutting) | Not Started | PR-01 | M | observability only, low |
| [PR-07](PR-07-rank-stability-ci.md) | Rank-stability + ties: surface CIs so a "tied" shortlist reads as tied | engine/breadth | Not Started | PR-02 | S | scoring-presentation, low |

> No padding: every spec above is grounded in a real defect or a real seam read
> in this repo (cited per-spec). The calibration-spine work (`PR-01`) is
> **cross-repo** into `timepoint-snag-bench` — per `feedback_cross_repo_pr_opening`
> the branch is pushed there but the director opens that PR manually.

## Recommended merge order

**Calibration-spine-first**, mirroring the GSS DAG. The spine (`PR-01`) is the
keystone everything anchors to; `PR-02` makes the score honest first so the
spine has something falsifiable to measure.

```
PR-02 (fail-closed scoring + per-metric confidence) ──┬─> PR-01 (CALIBRATION SPINE / KEYSTONE) ──┬─> PR-05 (Flash→Pro calibrated handoff)
       │                                              │                                          └─> PR-06 (score flight-recorder + drift canary)
       ├─> PR-03 (grounding pass: liveness + temporal + Clockchain anchor)
       └─> PR-07 (rank-stability CIs)

PR-04 (model-slug liveness guard)   (independent, early — guards every later PR)
```

Practical sequence: **PR-02 (make the score honest + fail-closed) → PR-01
(stand up the held-out calibration spine) → PR-03 (ground it) + PR-07 (ties) →
PR-05 (calibrated handoff to Pro) → PR-06 (observe drift)**, with **PR-04** run
early as the guard. **PR-02 makes the score honest; PR-01 makes it falsifiable
and comparable; PR-03 grounds it; PR-05 makes the breadth→depth seam a real
contract instead of a raw float; PR-06 keeps it honest over time.**

## How to use these specs

1. Pick the lowest-numbered `Not Started` PR whose dependencies are `Done`.
2. Read its spec end-to-end. **Files/modules to touch** and **Approach** are
   grounded in the current codebase (real paths in `timepoint-flash` and, where
   marked, `timepoint-snag-bench` / `timepoint-web-app` / `timepoint-flash-
   deploy-private-feb-2026`).
3. Branch with a distinctive scope-bearing name (never reuse a branch name —
   `feedback_branch_naming`). Implement against the **Acceptance criteria**.
4. Write tests per the **Test plan** — **no mocks** (`feedback_no_mocks`): the
   repo has `pytest` (`tests/unit`, `tests/integration`, `tests/e2e`). The
   **only** stubbable boundary is the LLM/provider HTTP call; every other path
   runs for real.
5. Open the PR with `.github/pull_request_template.md`; complete the Flash
   safety checklist (comparable-score? fail-closed? grounded? slug-validated?
   cost-capped? Stability-key-neutral? deploy-private surface noted?).
6. Flip this table's `Status` and the spec's `Status:` line when state changes.
