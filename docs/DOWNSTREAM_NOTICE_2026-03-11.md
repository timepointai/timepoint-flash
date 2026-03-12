# DOWNSTREAM NOTICE — 2026-03-11

**Breaking changes to `model_policy: "permissive"` and image generation**

Affects: Web App, iPhone App, Clockchain, Billing, Enterprise integrations

---

## What changed

### 1. Permissive mode now enforces open-weight models (BREAKING)

Previously, `model_policy: "permissive"` was advisory — it labeled model provenance in the response but did not block proprietary models. **It now enforces.**

If you send `model_policy: "permissive"` with an explicit `text_model` or `image_model` that is proprietary, the request will be rejected with **HTTP 422**:

```json
{
  "detail": "model_policy='permissive' requires open-weight models. 'openai/gpt-4o' is proprietary. Use models from: meta-llama/, deepseek/, qwen/, mistralai/, microsoft/, google/gemma, allenai/, nvidia/"
}
```

**Action required:** If you pass explicit model IDs alongside `model_policy: "permissive"`, ensure they are from the open-weight allowlist:

| Prefix | Examples |
|--------|----------|
| `meta-llama/` | `meta-llama/llama-4-scout-17b-16e-instruct` |
| `deepseek/` | `deepseek/deepseek-chat-v3-0324` |
| `qwen/` | `qwen/qwen3-235b-a22b`, `qwen/qwen3-30b-a3b` |
| `mistralai/` | `mistralai/mistral-small-3.2-24b-instruct` |
| `microsoft/` | Phi family |
| `google/gemma` | Gemma open-weight models only (not Gemini) |
| `allenai/` | OLMo family |
| `nvidia/` | Nemotron family |
| `black-forest-labs/` | FLUX image models (`flux.2-pro`, `flux.2-max`, `flux.2-flex`) |

If you omit `text_model` / `image_model` with permissive mode, Flash auto-selects the best available open-weight model from the registry. No action needed in that case.

### 2. Pollinations removed — all images via OpenRouter (BREAKING if you used `image_model: "pollinations"`)

Pollinations.ai has been removed entirely as an image provider. The image fallback chain is now:

- **Before:** Google → OpenRouter → Pollinations (3-tier)
- **After:** Google → OpenRouter (2-tier)

If you were passing `image_model: "pollinations"` in requests, this will now fall through to OpenRouter image models. Remove any explicit `"pollinations"` references.

### 3. Permissive mode is dramatically faster

Generation with `model_policy: "permissive"` was timing out at 600s due to DeepSeek R1 (a thinking model, 30-60s per call) being selected early in the fallback chain. Fixed:

- **Model preference reordered:** Fast chat models first (Llama 4 Scout, DeepSeek Chat V3, Qwen3-30B). DeepSeek R1 is now last resort.
- **Dialog batched:** Permissive mode uses batch dialog (1 LLM call) instead of sequential (7 calls).
- **Critique loop skipped:** Permissive mode skips the dialog critique/refinement pass.
- **Default max_tokens=2048:** Applied when no preset is specified, preventing unbounded generation.

Expected latency: ~2 minutes (down from 10+ minutes / timeout).

### 4. Google fallback blocked in permissive mode

The LLM router previously fell back to Google Gemini when OpenRouter calls failed, even in permissive mode. This violated the Google-free guarantee. The router now skips Google fallback entirely when `model_policy: "permissive"`.

---

## Migration checklist

- [ ] **Search for `"pollinations"` in your codebase** — remove any explicit references as an `image_model` value
- [ ] **If you send explicit models with `model_policy: "permissive"`** — verify they match the allowlist prefixes above, or handle 422 responses
- [ ] **If you had long timeouts for permissive mode** — you can likely reduce them (2-3 minutes is sufficient now)
- [ ] **No action needed if** you use `model_policy: "permissive"` without explicit model overrides — auto-selection handles everything

## Request examples

**Simplest permissive request (recommended):**
```json
{
  "query": "The signing of the Magna Carta, 1215",
  "generate_image": true,
  "model_policy": "permissive"
}
```

**Permissive with explicit open-weight model:**
```json
{
  "query": "Apollo 11 Moon Landing, 1969",
  "model_policy": "permissive",
  "text_model": "qwen/qwen3-235b-a22b",
  "generate_image": true
}
```

**This will now fail (422):**
```json
{
  "query": "D-Day, 1944",
  "model_policy": "permissive",
  "text_model": "openai/gpt-4o"
}
```

---

*Deployed to production: 2026-03-11*
*PR (open-source): https://github.com/timepointai/timepoint-flash/pull/16*
