# Downstream Model Control — TIMEPOINT Flash

**For teams building on TIMEPOINT Flash (Web App, iPhone App, Clockchain, Billing, Enterprise integrations)**

TIMEPOINT Flash now supports full downstream control of model selection and generation hyperparameters on every generation request. Downstream apps can set `model_policy: "permissive"` to route all 14 pipeline agents through open-weight models (DeepSeek, Llama, Qwen, Mistral) via OpenRouter for both text and images — making the entire pipeline fully Google-free with zero Google API calls, including grounding. Apps can also specify exact models by name using `text_model` and `image_model` (any OpenRouter-compatible model ID like `qwen/qwen3-235b-a22b` or Google native like `gemini-2.5-flash`), and these explicit overrides take priority over `model_policy`, which in turn takes priority over `preset`. In addition, the new `llm_params` object provides fine-grained control over generation hyperparameters — temperature, max_tokens, top_p, top_k, frequency/presence/repetition penalties, stop sequences, thinking level, and system prompt injection (prefix/suffix) — all applied uniformly across every agent in the pipeline. Request-level `llm_params` override each agent's built-in defaults, so setting `temperature: 0.3` overrides the scene agent's default of 0.7, the dialog agent's default of 0.85, etc. All of these controls are composable: you can combine `model_policy`, explicit models, `preset`, and `llm_params` in the same request.

## Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | Yes | Historical moment description (3-500 chars) |
| `generate_image` | boolean | No | Generate AI image (default: false) |
| `preset` | string | No | Quality preset: `hyper`, `balanced` (default), `hd`, `gemini3` |
| `text_model` | string | No | Text model ID — OpenRouter format (`org/model`) or Google native (`gemini-*`). Overrides preset. |
| `image_model` | string | No | Image model ID — OpenRouter format (`org/model`) or Google native. Overrides preset. |
| `model_policy` | string | No | `"permissive"` for open-weight only, Google-free generation. |
| `llm_params` | object | No | Fine-grained LLM hyperparameters (see table below). |
| `visibility` | string | No | `public` (default) or `private` |
| `callback_url` | string | No | URL to POST results when generation completes (async only) |
| `request_context` | object | No | Opaque context passed through to response |

## LLM Parameters (`llm_params`)

| Parameter | Type | Range | Providers | Description |
|-----------|------|-------|-----------|-------------|
| `temperature` | float | 0.0–2.0 | All | Sampling temperature. Overrides per-agent defaults (0.2 for factual, 0.85 for creative). |
| `max_tokens` | int | 1–32768 | All | Max output tokens per agent call. Preset defaults: hyper=1024, balanced=2048, hd=8192. |
| `top_p` | float | 0.0–1.0 | All | Nucleus sampling threshold. |
| `top_k` | int | >= 1 | All | Top-k sampling — consider only the k most likely tokens. |
| `frequency_penalty` | float | -2.0–2.0 | OpenRouter | Penalize tokens proportionally to frequency in output. |
| `presence_penalty` | float | -2.0–2.0 | OpenRouter | Penalize tokens that have appeared at all in output. |
| `repetition_penalty` | float | 0.0–2.0 | OpenRouter | Multiplicative penalty for repeated tokens. |
| `stop` | string[] | max 4 | All | Stop sequences — generation halts when produced. |
| `thinking_level` | string | — | Google | Reasoning depth: `"none"`, `"low"`, `"medium"`, `"high"`. |
| `system_prompt_prefix` | string | max 2000 | All | Text prepended to every agent's system prompt. |
| `system_prompt_suffix` | string | max 2000 | All | Text appended to every agent's system prompt. |

## Model Selection Priority (highest first)

1. Explicit `text_model` / `image_model`
2. `model_policy: "permissive"` (auto-selects open-weight models, skips Google grounding)
3. `preset` (uses preset's default models)
4. Server defaults

## Examples

**Google-free generation:**
```json
{
  "query": "The signing of the Magna Carta, 1215",
  "generate_image": true,
  "model_policy": "permissive"
}
```

**Specific model with custom params:**
```json
{
  "query": "Turing breaks Enigma, 1941",
  "text_model": "deepseek/deepseek-r1-0528",
  "llm_params": {
    "temperature": 0.5,
    "max_tokens": 4096,
    "top_p": 0.9,
    "system_prompt_suffix": "Keep all descriptions under 200 words. Use British English."
  }
}
```

**Permissive mode with explicit model override:**
```json
{
  "query": "Apollo 11 Moon Landing, 1969",
  "model_policy": "permissive",
  "text_model": "qwen/qwen3-235b-a22b",
  "generate_image": true
}
```

---

*Last updated: 2026-03-11*
