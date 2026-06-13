# PR-05 — Flash→Pro calibrated handoff contract (breadth-rank → depth-select)

**Layer-fit:** engine (the breadth↔depth seam) · **Status: Not Started**
(**cross-repo** — web-app + pro-cloud) · **Depends on:** PR-01, PR-02 ·
**Effort:** M · **Cost/risk:** cross-repo contract, medium.

> **Shared pattern with GSS / Clockchain — one engine, one scale.** The program
> map calls Flash the *breadth* tier and GSS/Pro the *depth* tier of **one
> simulation engine**. Today the seam between them is a lossy raw-float pass:
> the web-app's deep-sim handoff (`_pro_cloud_create_run` in
> `timepoint-web-app/app/find_money/runs/jobs.py`) sends Pro Cloud only
> `tdf_ref` + `tdf` + a `scenario_description` (derived from the quick-sim
> `rationale`/`summary`) and **drops the Flash scores entirely** — Pro Cloud
> rebuilds from `strategy_axes`, so a Flash `probability_of_award` and a Pro
> deep-sim `probability` are **never on the same scale and never reconciled**.
> Worse, when Pro Cloud is unreachable, the web-app surfaces Flash's raw
> quick-sim scores **as if they were the deep-sim result**
> (`_quick_sim_derived_results` → `_seed_deep_sim_results`). The breadth→depth
> seam must be a **first-class, calibrated contract**, not a silent
> rescale/relabel.

## Goal
Define and implement the Flash→Pro handoff as an **explicit, calibrated
contract**: Flash emits, per opportunity, a *breadth-tier* score with its
**confidence**, **basis**, and **calibration provenance** (which spine version
calibrated it — PR-01); Pro consumes it as a *prior* and returns a *depth-tier*
score **on the same scale** (the shared PR-01 / GSS-`PR-02` scorer), so the two
are comparable and the user is never shown a breadth score mislabeled as a
depth score.

## Scope
**In:**
- **A typed handoff payload** carried from Flash quick-sim into the deep-sim
  request. Extend the quick-sim entry (`QuickSimTdfEntry` in
  `app/schemas/quick_sim.py`) so the web-app can forward — not drop — the
  Flash score + `score_confidence` + `confidence_basis` (PR-02) + a
  `calibration_ref` (which PR-01 spine version produced the scale) +
  grounding facts (PR-03). These are the breadth-tier *prior*.
- **Pro consumes the prior + returns on the same scale.** The web-app
  `_pro_cloud_create_run` payload gains the breadth prior alongside each
  `tdf_ref`; Pro Cloud records it and returns its deep-sim `probability` on the
  **same calibrated scale** (the shared PR-01/GSS-`PR-02` scorer) so a consumer
  can honestly say "breadth said 0.4±0.2, depth said 0.55±0.08" — a refinement,
  not a contradiction-with-no-context.
- **Honest labeling when Pro is skipped.** When the deep-sim is not run, the
  result the user sees must be **labeled a breadth-tier estimate with its
  confidence**, not silently presented as a deep-sim result
  (fix `_quick_sim_derived_results` / `_seed_deep_sim_results` labeling).
- **Selection uses the calibrated breadth rank.** The top-N the user shortlists
  for the expensive Pro spend is ranked on the *calibrated, confidence-aware*
  Flash score (PR-01 + PR-02 + PR-07), not the raw 0–1 float — spending depth
  budget on the breadth tier's best-grounded bets.

**Out:**
- The Pro-side deep-sim scoring internals (GSS queue — this spec defines the
  *contract* + the scale Pro returns on, not Pro's mechanism math).
- Re-metering / billing changes (the gateway + `on_behalf_of_user_id` act-as
  contract is unchanged; do not touch metering).
- Building the calibration scale itself (**PR-01**, prerequisite).

## Files / modules touched
- **`timepoint-flash` (engine):** `app/schemas/quick_sim.py` —
  `QuickSimTdfEntry` (~L164–211): add the typed handoff fields
  (`score_confidence`, `confidence_basis`, `calibration_ref`,
  `grounding_facts`) so the breadth prior is *carried*, not dropped (additive /
  optional — preserves `_seed_quick_sim_tdfs` pairing).
- **`timepoint-web-app` (cross-repo):** `app/find_money/runs/jobs.py` —
  `_pro_cloud_create_run` (~L413–490): forward the breadth prior into the
  `/api/runs` payload instead of discarding it; `_quick_sim_derived_results` /
  `_seed_deep_sim_results` (~L511+): label the no-deep-sim result as a
  breadth-tier estimate with confidence.
- **`timepoint-pro-cloud-private` (cross-repo):** `/api/runs` `TDFSpec` /
  the run result schema: accept the breadth prior; return the deep-sim
  `probability` on the shared calibrated scale (coordinate with GSS `PR-02`).

## Approach
1. **Carry, don't drop.** Flash entry gains the prior fields; the web-app
   forwards them into the Pro Cloud request.
2. **One scale.** Pro returns its score on the PR-01/GSS-`PR-02` scale so
   breadth and depth are directly comparable (refinement, not relabel).
3. **Label honestly.** No-deep-sim path is explicitly a breadth estimate + its
   confidence; never masquerades as a deep-sim result.
4. **Rank on the calibrated score.** Selection orders by the confidence-aware
   calibrated breadth score so the depth budget goes to the best-grounded bets.

## Acceptance criteria
- The quick-sim entry carries the breadth prior (`score` + `score_confidence` +
  `confidence_basis` + `calibration_ref` + `grounding_facts`); existing
  `_seed_quick_sim_tdfs` pairing is unbroken (additive/optional).
- The web-app deep-sim request forwards the breadth prior to Pro Cloud instead
  of dropping it.
- Pro Cloud returns its deep-sim probability on the **same calibrated scale** as
  the Flash breadth score (verified via the shared PR-01 scorer).
- When Pro is skipped, the user-facing result is labeled a breadth-tier estimate
  with its confidence — never presented as a deep-sim result.
- Selection ranks on the calibrated, confidence-aware breadth score.

## Test plan (no mocks)
- `timepoint-flash` `tests/unit`: the entry serialises the prior fields;
  defaults keep the old pairing shape.
- `timepoint-web-app` `tests/`: `_pro_cloud_create_run` payload includes the
  breadth prior; the no-deep-sim path produces a breadth-labeled result (assert
  the label/flag, not a "placeholder" or a deep-sim claim).
- Cross-repo integration (Pro Cloud hit real, LLM boundary capped): a handoff
  round-trips the prior and returns a deep-sim score on the shared scale.
- `pytest` green in each repo.

## Cost / safety
No new per-user LLM cost (the prior is data already computed). Stability-key-
neutral. **Cross-repo:** branches pushed in web-app + pro-cloud; the director
opens those PRs manually (`feedback_cross_repo_pr_opening`). pro-cloud vendors
pro-internal via subtree — coordinate the scale change with GSS `PR-02`. No
Flash deploy-private surface (the Flash change is open-source-repo schema).

## Dependencies / merge order
**After PR-01** (the shared scale must exist) **and PR-02** (the confidence the
prior carries). The breadth↔depth seam of **one engine** — coordinate with GSS
`PR-02` so both tiers report on the identical scale.

## Status: Not Started
