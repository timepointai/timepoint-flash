# PR-04 — Model-slug liveness guard (fail loud on dead depth / frontier slugs)

**Layer-fit:** engine / breadth tier (guard rail) · **Status: Not Started** ·
**Depends on:** none · **Effort:** S · **Cost/risk:** ~1 catalog call/run, low.

> **Shared pattern with GSS — this is the SAME guard.** GSS `PR-00c`
> ("Model-slug liveness guard") exists because dead OpenRouter slugs silently
> 404 → empty/garbled sims. The exact failure mode is documented ecosystem-wide
> in `reference_dead_model_slug_failure_mode.md` (the Pro engine was bitten by
> a dated `claude-3-5-haiku-…` slug). Flash has the **same exposure**:
> `VerifiedModels` (`app/config.py` L88–139) is a **static hardcoded list** —
> `gemini-2.0-flash`, `google/gemini-3-flash-preview`,
> `anthropic/claude-opus-4.8`, etc. — with **no liveness check**, and the
> `frontier` depth tier routes to `anthropic/claude-opus-4.8` via OpenRouter.
> When one of those slugs is silently deprecated, the quick-sim batch returns
> empty/garbled scores and the user pays for noise.

## Goal
Validate that the model slug a quick-sim run resolves to is **actually live**
before the batch runs, and **fail loud** (clear error, refund, flag) rather than
emitting silent empty/garbled scores. Specifically guard the `depth`-dial
resolution (`find_money.py::_resolve_quick_sim_text_model` /
`_DEPTH_TO_TEXT_MODEL`) and the `VerifiedModels` static lists.

## Scope
**In:**
- A **liveness check** that confirms a resolved slug exists in the live provider
  catalog. The repo already has the seam: `app/core/model_registry.py::
  OpenRouterModelRegistry.is_model_available` (used by
  `VerifiedModels.is_verified_or_available`, `config.py` L197–206) — extend it
  so the *static* `VerifiedModels` lists are also liveness-checkable, not just
  the dynamic-registry path, and cache the catalog (one call/run, not per-opp).
- Wire the check into the quick-sim model resolution
  (`_resolve_quick_sim_text_model`): if the resolved slug (default
  `gemini-2.5-flash`, or a `depth`-dial slug like `gemini-2.0-flash` /
  `anthropic/claude-opus-4.8`) is **not live**, either (a) fall back to a
  known-live default with a loud WARNING, or (b) for `frontier`, fail the
  affected opportunity with an honest error + refund — **never** proceed to emit
  garbage scores.
- A startup / CI assertion that every slug in `VerifiedModels.GOOGLE_TEXT`,
  `OPENROUTER_TEXT`, `_DEPTH_TO_TEXT_MODEL`, and the fallback chains resolves
  live — so a dead slug is caught in CI, not in production.

**Out:**
- Image-model slugs / the Stability path (quick-sim doesn't render images
  inline; out of scope here — but note the same guard should later cover
  `GOOGLE_IMAGE` / `STABILITY_IMAGE` to protect the Stability-key isolation).
- Re-architecting the registry (just extend the existing `is_model_available`
  seam).

## Files / modules touched
- `app/config.py` — `VerifiedModels` (~L88–208): add a classmethod that
  liveness-checks the static lists via the model registry; the
  `is_verified_or_available` seam already exists (L176–208) — generalise it.
- `app/core/model_registry.py` — `OpenRouterModelRegistry.is_model_available` /
  catalog cache: ensure a single bounded catalog fetch/run, and a Google-native
  catalog check for `GOOGLE_TEXT` slugs.
- `app/api/v1/find_money.py` — `_resolve_quick_sim_text_model` (~L171–190): add
  the liveness guard with loud-fallback / fail-loud behavior; `_simulate_one`
  refunds + flags an opportunity whose `frontier` slug is dead.
- A CI test (`tests/`) asserting all configured slugs resolve live.

## Approach
1. **One catalog fetch/run, cached.** Liveness is a set-membership check against
   a cached live catalog — not a per-opportunity call.
2. **Guard the resolver.** Default/`standard`/`deep`/`fast` → loud fallback to a
   known-live model; `frontier` → fail the opportunity loud + refund rather than
   silently degrade a paid frontier request to garbage.
3. **Catch in CI.** A test enumerates every configured slug and asserts it
   resolves live — the dead-slug failure mode becomes a red CI, not a silent
   prod regression (the ecosystem alarm is CI red — `feedback_no_slack`).

## Acceptance criteria
- A resolved quick-sim slug is liveness-checked before the batch runs (one
  cached catalog fetch/run, not per-opportunity).
- A dead default/standard slug → loud WARNING + fallback to a live model; a dead
  `frontier` slug → that opportunity fails with an honest error + refund, never
  emits a garbage score.
- A CI test fails loudly if any slug in `VerifiedModels` /
  `_DEPTH_TO_TEXT_MODEL` / the fallback chains is dead.

## Test plan (no mocks)
- `tests/unit`: the liveness classmethod against a real (cached) catalog fixture
  — a known-live slug passes, a fabricated slug fails.
- `tests/integration` (provider catalog hit real or capped): `_resolve_quick_sim
  _text_model` falls back loudly on a dead non-frontier slug; a dead frontier
  slug yields a failed+refunded opportunity, not a garbage score.
- `tests/` CI guard: enumerate all configured slugs, assert each resolves live.

## Cost / safety
One bounded catalog fetch per run (cached), no per-opportunity cost.
Stability-key-neutral. Pure guard — reversible, additive. Lands in the
open-source repo; the registry/catalog auth is the same as today.

## Dependencies / merge order
**Independent — run early.** Guards every later PR (a dead slug poisons the
calibration spine's inputs too). Mirrors GSS `PR-00c`; the two guards share the
same failure mode and should stay conceptually identical across the engine.

## Status: Not Started
