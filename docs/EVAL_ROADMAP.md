# Eval System Roadmap

Future enhancements for the TIMEPOINT Flash evaluation system.

---

## Current State (v2.4.0)

- Multi-model latency comparison (`/api/v1/eval/compare`)
- Presets: verified, google_native, openrouter, all
- CLI: `eval.sh` with interactive mode
- Metrics: latency (min/max/avg/median), success rate, ranking
- 522 fast tests + integration tests + e2e tests (600+ total)
- Google Search grounding for historical accuracy
- 3-tier image fallback (Google → OpenRouter → Pollinations.ai)
- Physical presence detection for accurate image generation
- Model tracking (`text_model_used`, `image_model_used` in responses)
- Image URL populated as data URI when image generation succeeds
- CritiqueAgent: post-dialog review for anachronisms, cultural errors, voice issues (auto-retry)
- Voice differentiation: social register constraints per character class (elite/educated/common/servant/child)
- Emotional transfer: image prompt optimizer translates tension_arc into physicalized body language
- Grounding→CharacterID pipeline: verified participants inform character casting and naming
- Graph pruning: relationship cap at 2x characters, salience threshold, no background-to-background pairs
- Character cap reduced to 6 for higher per-character quality
- Visibility system: public/private timepoints with server-enforced access control
- Share URLs: configurable `SHARE_URL_BASE` generates shareable links for public scenes
- Auth-gated interactions: chat, dialog, survey endpoints require JWT when `AUTH_ENABLED=true`

**Gap**: Measures speed only, not quality.

---

## Observed Benchmark Data

Results from live eval runs against the `verified` preset (4 models):

### Run 1: "battle of thermopylae 480 BCE"

| Model | Provider | Latency | Status |
|-------|----------|---------|--------|
| `google/gemini-3-flash-preview` | OpenRouter | ~6.5s | Fastest |
| `google/gemini-2.0-flash-001` | OpenRouter | ~8.3s | OK |
| `gemini-2.5-flash` | Google | ~12.9s | OK |
| `gemini-2.5-flash` (thinking) | Google | ~15.9s | OK |

- **4/4 successful**, total wall time: ~16s
- Fastest: `gemini-3-flash-preview`
- Slowest: `gemini-2.5-flash` (thinking mode)

### Run 2: "the moment Oppenheimer witnessed the first nuclear detonation"

| Model | Provider | Latency | Status |
|-------|----------|---------|--------|
| `google/gemini-3-flash-preview` | OpenRouter | ~6.9s | Fastest |
| `google/gemini-2.0-flash-001` | OpenRouter | ~8.1s | OK |
| `gemini-2.5-flash` | Google | ~23.3s | OK |
| `gemini-2.5-flash` (thinking) | Google | N/A | 429 RESOURCE_EXHAUSTED |

- **3/4 successful**, total wall time: ~23s
- Google quota exhaustion caused one failure (immediate, no retries wasted)
- OpenRouter models unaffected by Google quota

### Key Findings

1. **`gemini-3-flash-preview` is consistently the fastest model** (~6-7s), outperforming even `gemini-2.0-flash` by 20-30%
2. **Google native API models are slower** than the same models through OpenRouter (~13-23s vs ~6-8s)
3. **Google quota exhaustion is intermittent** – one run may succeed while the next hits 429 errors
4. **OpenRouter provides more reliable throughput** – unaffected by Google API quota limits
5. **Thinking mode adds significant latency** – `gemini-2.5-flash` thinking is 2-3x slower than standard

---

## Enhancement Pathways

### A. Quality Scoring (LLM-as-Judge)

Score outputs on domain-specific dimensions:
- Historical accuracy
- Temporal consistency
- Character authenticity
- Dialog period-appropriateness
- Anachronism detection

**Endpoint**: `POST /api/v1/eval/quality`

---

### B. Pipeline Evaluation

Test full 14-agent pipeline, not just raw text:
- Step-by-step timing
- Schema validation per step
- Error rate tracking
- Completeness checks

**Endpoint**: `POST /api/v1/eval/pipeline`

---

### C. Benchmark Dataset

Golden test set for regression testing:
```
evals/
├── datasets/
│   ├── golden_queries.json    # 50 curated queries
│   ├── ground_truth.json      # Expected facts
│   └── edge_cases.json        # BCE dates, obscure events
└── baselines/
    └── v2.2.1_results.json
```

**CLI**: `./eval.sh --regression`

---

### D. Cost Tracking

- Token counting (input/output)
- Cost estimation per model
- Cost/quality efficiency ratio

---

### E. Historical Accuracy Checker

Domain-specific validation:
- Character existence verification
- Date plausibility
- Location accessibility
- Anachronism detection in dialog

---

### F. Persistent Results + Dashboard

- Store eval runs in database
- Track results over time
- Compare runs (A/B testing)
- CI integration

---

## Architecture Comparison Eval

**Core question**: Can one frontier model one-shot what 14 specialized agents produce?

### The Matchup

| Mode | Description |
|------|-------------|
| **Pipeline** | 14 agents (Flash/2.0), parallel execution, specialized prompts |
| **Monolith** | 1 frontier model (Opus 4.5, GPT-4o), single mega-prompt |

### Comparison Dimensions

| Dimension | Pipeline | Monolith |
|-----------|----------|----------|
| Latency | ~15-30s | ~10-20s |
| Cost | ~$0.02 | ~$0.15-0.30 |
| Reliability | Graceful degradation | Single point of failure |
| Quality | Specialized prompts | General capability |

### Quality Judging

Use LLM judge to score both outputs:
- Historical accuracy
- Character depth
- Dialog authenticity
- Scene vividness
- Narrative coherence
- Schema completeness

### Frontier Models to Test

- Claude Opus 4.5
- GPT-4o
- Gemini 2.5 Pro
- Claude Sonnet 4

### Output

```
VERDICT: Pipeline wins on quality (8.9 vs 8.6)
         Monolith wins on speed (32% faster)
         Pipeline wins on cost (13x cheaper)
```

**Endpoint**: `POST /api/v1/eval/architecture/compare`
**CLI**: `./eval.sh --architecture "query"`

---

## Priority Matrix

| Pathway | Effort | Value | Priority |
|---------|--------|-------|----------|
| B. Pipeline Eval | 2d | High | 1 |
| A. Quality Scoring | 2-3d | High | 2 |
| Architecture Comparison | 3-4d | High | 3 |
| C. Benchmark Dataset | 3-4d | High | 4 |
| D. Cost Tracking | 1d | Medium | 5 |
| F. Persistent Results | 2-3d | Medium | 6 |
| E. Historical Checker | 4-5d | High | 7 |

---

## Research Questions

1. Does specialization beat generalization?
2. Is frontier model overhead worth the cost?
3. Where do monolith models fail? (dialog? relationships?)
4. Can we hybrid? (frontier for some steps, small for others)
5. What's the optimal cost/quality trade-off point?

---

## Known Issues

Issues discovered during testing that affect functionality:

### 1. No API `preset: "free"` Option

**Issue:** The API does not have a built-in `preset: "free"` parameter option.

**Current Support:**
- **CLI (demo.sh)**: Full free model support via preset options 5/6 ("Free Best"/"Free Fastest") and "RAPID TEST FREE" menu option
- **API**: Use `text_model` override with free model IDs from `/api/v1/models/free` (e.g., `google/gemini-2.0-flash-001:free`)

**Enhancement:** Add a "free" preset to the API for consistency with CLI.

---

### 2. Fallback Direction

**Issue:** The fallback logic goes free → paid models, but not paid → free. When paid models fail (e.g., rate limits), the system doesn't try free alternatives.

**Enhancement:** Add configurable fallback to include free models as last resort.

---

### Fixed Issues (v2.3.1)

The following issues were discovered and fixed during comprehensive testing:

1. **Temporal sequence endpoint crash** - `GET /temporal/{id}/sequence` returned 500 error ("Multiple rows found") when a timepoint had multiple children. Fixed by selecting the most recent child with `ORDER BY created_at DESC LIMIT 1`.

2. **SQLAlchemy cartesian product warning** - Pagination count query in `list_timepoints` produced cartesian product warnings. Fixed by using `func.count()` with proper `select_from(subquery)`.

3. **Model tracking** - `text_model_used` and `image_model_used` were not tracked in responses. Added fields to the Timepoint model and populated them from the pipeline's router config.

4. **image_url not populated** - `image_url` was always null even after successful image generation. Fixed by generating a data URI from `image_base64` in the pipeline.

5. **Async `/generate` endpoint ignored request parameters** - `run_generation_task()` didn't pass `generate_image`, `preset`, `text_model`, or `image_model` to the pipeline — it always ran with defaults. Fixed by threading request params through `run_generation_task()`.

6. **Async `/generate` background task didn't persist image data** - `image_base64`, `image_model_used`, and `slug` were not copied to the DB after background generation — generated images were silently discarded. Fixed by adding missing field assignments in the DB update loop.

7. **Temporal navigation never generated images** - `generate_moment_from_context()` called `pipeline.run()` without `generate_image=True`, so `/temporal/{id}/next` and `/prior` never produced images. Fixed.

### Quality Enhancements (v2.3.2)

Addressing critique feedback on dialog quality (3/10), historical accuracy (5/10), and image emotional flatness (6.5/10):

8. **CritiqueAgent abstraction** — New `app/agents/critique.py` reviews dialog output for anachronisms (material, linguistic), cultural errors (Greek vs Roman deities, modern idioms), voice distinctiveness, and timeline accuracy. When critical issues found, dialog re-runs with revision instructions injected. One retry max.

9. **Voice differentiation by social register** — Character identification now assigns social registers (elite/educated/common/servant/child). Bio prompts enforce class-appropriate sentence structure, vocabulary level, and verbal tics. Sequential dialog prompts require each character to be "identifiable by voice alone." Modern idioms explicitly prohibited.

10. **Emotional transfer in image optimizer** — Optimizer no longer strips emotion. Instead translates `tension_arc` and `emotional_beats` into physicalized visual cues (body language, facial expressions, environmental urgency). Target reduced from 120 to 77 words (~100 tokens). Goal changed from "illustration" to "caught moment."

11. **Grounding feeds character identification** — Grounding agent's `verified_participants` and `setting_details` now flow into `CharacterIdentificationInput`. Prevents literary pattern-matching (e.g., naming a random Roman woman "Fortunata" from Petronius's Satyricon). Naming rules enforce period-authentic identifiers or generic role-based names.

12. **Graph relationship pruning** — Relationships capped at 2x character count. Neutral/stranger pairs omitted. Background-to-background relationships prohibited. Only relationships that affect dialog or visual composition are included.

### Pipeline + Dialog Enhancements (v2.3.3)

13. **`text_model_used` not copied in background task** — The `/generate` async endpoint never stored `text_model_used` because it was missing from the field-copy loop in `run_generation_task()`. Fixed.

14. **`social_register` missing from CharacterStub schema** — The prompt asked for social register but the schema had no field, so the LLM output was silently dropped. Added `social_register: str | None` to `CharacterStub`.

15. **Grounding trigger too restrictive** — `needs_grounding()` required BOTH `query_type == HISTORICAL` AND `detected_figures > 0`. If the Judge didn't extract supporting musicians (e.g., Billy Cox, Larry Lee at Woodstock), grounding was skipped entirely. Fixed: grounding now triggers for any HISTORICAL query — the grounding agent discovers participants itself via Google Search.

16. **Grounding + moment data not stored in DB** — `grounding_data_json` and `moment_data_json` had no DB columns, so they were lost after generation. Added columns + alembic migration, stored from `state_to_timepoint()`, and exposed in API response when `include_full=True`.

17. **Grounding context not fully passed to character ID** — `CharacterIdentificationInput.from_data()` only extracted `physical_participants` and `setting_details` from grounding. Now also extracts `verified_participants`, `verified_location`, `verified_date`, and `event_mechanics` for richer character identification context.

18. **Character validator cap 8→6** — `CharacterIdentification` validator allowed up to 8 characters, inconsistent with the stated cap of 6. Fixed to truncate at 6 while preserving priority order (primary > secondary > background).

19. **Narrative arc dialog system** — New `app/schemas/dialog_arc.py` implements Vonnegut's 6 story shapes + Freytag's pyramid. Maps MomentData's `tension_arc` to a narrative shape, assigns 7 beats with functions (establish/complicate/escalate/turn/react/resolve/punctuate), intensity curves, and speaker roles. Dialog agent uses arc-aware speaker selection: TURN → focal character, REACT → different character, PUNCTUATE → background outsider. Forces dialog complexity to O(n) instead of O(2^n).

20. **MomentData + relationships wired into dialog** — `DialogInput.from_data()` now accepts `moment` parameter. Narrative context (stakes, central question, conflict) injected into first-turn prompts. Relationship context injected into response prompts. Speaker limit expanded from 4 to 6 (arc manages coherence).

---

*Last updated: 2026-02-16*
