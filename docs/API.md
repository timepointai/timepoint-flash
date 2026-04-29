# API Reference

Base URL: `http://localhost:8000`

Interactive docs: [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)

---

## Quick Examples

**Generate a scene (streaming - recommended):**
```bash
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "Oppenheimer Trinity test control bunker 5:29 AM July 16 1945", "preset": "hyper", "generate_image": true}'
```

**Chat with a character:**
```bash
curl -X POST http://localhost:8000/api/v1/interactions/{timepoint_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character": "Oppenheimer", "message": "What did you feel when the sky turned white?"}'
```

**Jump forward in time:**
```bash
curl -X POST http://localhost:8000/api/v1/temporal/{timepoint_id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "hour"}'
```

---

## Quality Presets

Control the speed/quality tradeoff with presets:

| Preset | Speed | Quality | Text Model | Provider |
|--------|-------|---------|------------|----------|
| **hyper** | ~55s | Good | `google/gemini-2.0-flash-001` | OpenRouter |
| **balanced** | ~90-110s | Better | `gemini-2.5-flash` | Google Native |
| **hd** | ~120-150s | Best | `gemini-2.5-flash` (extended thinking) | Google Native |
| **gemini3** | ~60s | Excellent | `google/gemini-3-flash-preview` | OpenRouter |

> **Note on `hyper`:** the hyper preset is **text-only**. `generate_image: true` is silently ignored — responses will return `has_image: false` and no `image_url`. Use `balanced`, `hd`, or `gemini3` if you need an image. 

**Usage:**
```json
{
  "query": "Turing interrogation Wilmslow February 1952",
  "preset": "hyper",
  "generate_image": false
}
```

**Model Overrides:**

Override preset models for custom configurations:
```json
{
  "query": "Zheng He treasure fleet Malindi harbor 1418",
  "text_model": "google/gemini-2.0-flash-001",
  "image_model": "gemini-2.5-flash-image"
}
```

**Permissive Mode (Google-Free):**

Use only open-weight, distillable models — zero Google API calls:
```json
{
  "query": "The signing of the Magna Carta, 1215",
  "generate_image": true,
  "model_policy": "permissive"
}
```
Text routes to DeepSeek/Llama/Qwen via OpenRouter, images route to OpenRouter (Flux/Gemini), and Google grounding is skipped. Response metadata reflects the actual models used:
```json
{
  "text_model_used": "deepseek/deepseek-chat-v3-0324",
  "image_model_used": "google/gemini-2.5-flash-image-preview",
  "model_provider": "openrouter",
  "model_permissiveness": "permissive"
}
```

**Composing model_policy with explicit models:**

`model_policy` and explicit model names are composable — explicit models take priority:
```json
{
  "query": "Apollo 11 Moon Landing, 1969",
  "model_policy": "permissive",
  "text_model": "qwen/qwen3-235b-a22b",
  "generate_image": true
}
```
This uses the specified Qwen model for text, OpenRouter for images (from permissive policy), and skips Google grounding.

---

## LLM Parameters

The `llm_params` object gives downstream callers fine-grained control over generation hyperparameters. All fields are optional — unset fields use agent/preset defaults. These parameters are applied to every agent in the 14-step pipeline.

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

| Parameter | Type | Range | Providers | Description |
|-----------|------|-------|-----------|-------------|
| `temperature` | float | 0.0–2.0 | All | Sampling temperature. Overrides per-agent defaults (which range from 0.2 for factual agents to 0.85 for creative agents). |
| `max_tokens` | int | 1–32768 | All | Maximum output tokens per agent call. Preset defaults: hyper=1024, balanced=2048, hd=8192. |
| `top_p` | float | 0.0–1.0 | All | Nucleus sampling — only consider tokens whose cumulative probability is <= top_p. |
| `top_k` | int | >= 1 | All | Top-k sampling — only consider the k most likely tokens at each step. |
| `frequency_penalty` | float | -2.0–2.0 | OpenRouter | Penalize tokens proportionally to how often they've appeared in the output. |
| `presence_penalty` | float | -2.0–2.0 | OpenRouter | Penalize tokens that have appeared at all in the output so far. |
| `repetition_penalty` | float | 0.0–2.0 | OpenRouter | Multiplicative penalty for repeated tokens. |
| `stop` | string[] | max 4 | All | Stop sequences — generation halts when any of these strings is produced. |
| `thinking_level` | string | — | Google | Reasoning depth for thinking models: `"none"`, `"low"`, `"medium"`, `"high"`. |
| `system_prompt_prefix` | string | max 2000 | All | Text prepended to every agent's system prompt. Use for tone, persona, or style injection. |
| `system_prompt_suffix` | string | max 2000 | All | Text appended to every agent's system prompt. Use for constraints, formatting rules, or output instructions. |

**Notes:**
- Parameters marked "OpenRouter" are silently ignored when the request routes to Google (and vice versa for `thinking_level`).
- `system_prompt_prefix` and `system_prompt_suffix` affect all 14 pipeline agents. Use these to inject cross-cutting concerns (e.g., language, tone, verbosity constraints).
- Request-level `llm_params` override per-agent defaults. For example, if `llm_params.temperature` is set, it overrides the judge agent's default of 0.3, the scene agent's default of 0.7, etc.

---

## Endpoints Overview

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Auth** | `POST /api/v1/auth/apple` | Apple Sign-In → JWT pair |
| **Auth** | `POST /api/v1/auth/dev/token` | Dev admin: create test user → JWT pair |
| **Auth** | `POST /api/v1/auth/refresh` | Rotate refresh token |
| **Auth** | `GET /api/v1/auth/me` | Current user profile |
| **Auth** | `POST /api/v1/auth/logout` | Revoke refresh token |
| **Auth** | `DELETE /api/v1/auth/account` | Soft-delete user account |
| **Credits** | `GET /api/v1/credits/balance` | Current credit balance |
| **Credits** | `GET /api/v1/credits/history` | Paginated transaction ledger |
| **Credits** | `POST /api/v1/credits/admin/grant` | Dev admin: grant credits to any user |
| **Credits** | `GET /api/v1/credits/costs` | Credit cost table |
| **Users** | `GET /api/v1/users/me/timepoints` | User's timepoints (paginated) |
| **Users** | `GET /api/v1/users/me/export` | Full GDPR data export |
| **Users** | `POST /api/v1/users/resolve` | Find or create user by external_id (service-key protected) |
| **Generate** | `POST /api/v1/timepoints/generate/stream` | Create a scene (streaming) - **recommended** |
| **Generate** | `POST /api/v1/timepoints/generate/sync` | Create a scene (blocking) |
| **Generate** | `POST /api/v1/timepoints/generate` | Create a scene (background task) |

All generation endpoints run a 14-agent pipeline with critique loop: dialog is reviewed for anachronisms, cultural errors, and voice distinctiveness, and retried if critical issues are found. Characters are capped at 6 with social register-based voice differentiation. Image prompts translate narrative emotion into physicalized body language (~77 words).

When `AUTH_ENABLED=true`, generation, chat, dialog, survey, and temporal endpoints require a Bearer JWT and deduct credits. Private timepoints return 403 for non-owners. See [iOS Integration Guide](IOS_INTEGRATION.md) for full details.

| **Get** | `GET /api/v1/timepoints/{id}` | Retrieve a scene |
| **Chat** | `POST /api/v1/interactions/{id}/chat` | Talk to a character |
| **Time Travel** | `POST /api/v1/temporal/{id}/next` | Jump forward |
| **Time Travel** | `POST /api/v1/temporal/{id}/prior` | Jump backward |
| **Models** | `GET /api/v1/models/free` | List free OpenRouter models |
| **Eval** | `POST /api/v1/eval/compare` | Compare model latencies |
| **Eval** | `POST /api/v1/eval/compare/report` | Compare with formatted report |
| **Eval** | `GET /api/v1/eval/models` | List eval models and presets |

---

## Timepoints

### POST /api/v1/timepoints/generate/stream (Recommended)

Generate a scene with real-time progress updates via Server-Sent Events (SSE). **This is the recommended generation endpoint for any client that cannot block for 30–150s on a single HTTP request — specifically MCP tool calls, LLM agent loops, browser clients, and any proxy/gateway with a short read timeout.** The stream emits a keep-alive `step_complete` event roughly every 5–30s, which prevents idle-connection timeouts on upstream proxies.

**Response headers:**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**Request body:**
```json
{
  "query": "Oppenheimer watches the Trinity test 5:29 AM July 16 1945",
  "preset": "hyper",
  "generate_image": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | Historical moment (3-500 chars) |
| generate_image | boolean | No | Generate AI image (default: false) |
| preset | string | No | Quality preset: `hd`, `hyper`, `balanced` (default), `gemini3` |
| text_model | string | No | Text model ID — OpenRouter format (`org/model`) or Google native (`gemini-*`). Overrides preset. |
| image_model | string | No | Image model ID — OpenRouter format (`org/model`) or Google native. Overrides preset. |
| model_policy | string | No | `"permissive"` — selects only open-weight models (Llama, DeepSeek, Qwen) and skips Google-dependent steps. Fully Google-free. Works alongside explicit model overrides. |
| llm_params | object | No | Fine-grained LLM parameters applied to all pipeline agents. See **LLM Parameters** below. |
| visibility | string | No | `public` (default) or `private` — controls who can see full data |
| callback_url | string | No | URL to POST results to when generation completes (async endpoint only) |
| request_context | object | No | Opaque context passed through to response (e.g. `{"source": "clockchain", "job_id": "..."}`) |

**Model selection priority** (highest first):
1. Explicit `text_model` / `image_model` — use exactly these models
2. `model_policy: "permissive"` — auto-select open-weight models, skip Google grounding
3. `preset` — use preset's default models
4. Server defaults

#### Event schema

Every event is delivered as one SSE `data:` line containing a single JSON object, followed by a blank line (the standard SSE message terminator):

```
data: {"event": "step_complete", "step": "judge", "data": {"latency_ms": 1234, "model_used": "gemini-2.5-flash"}, "progress": 10, "error": null}
\n
```

All events share the same envelope (see `StreamEvent` in `app/api/v1/timepoints.py`):

| Field | Type | Always present | Description |
|-------|------|----------------|-------------|
| `event` | string | Yes | One of `start`, `step_complete`, `step_error`, `done`, `error` |
| `step` | string \| null | No | Pipeline step label (see table below). `null` on some fatal `error` events. |
| `data` | object \| null | No | Event-specific payload. See per-event tables. |
| `progress` | int | Yes | 0–100. Monotonic except on fatal `error` (sent as `0`). |
| `error` | string \| null | No | Human-readable error message. Present on `step_error` and `error`; `null` otherwise. |

**Event types:**

| `event` value | When | Terminal? | Payload |
|---|---|---|---|
| `start` | First event, after the pipeline is constructed | No | `data = {query, generate_image, preset}` |
| `step_complete` | After each successful pipeline step | No | `data = {latency_ms, model_used}` |
| `step_error` | A pipeline step failed but the pipeline continues (e.g. optional step) | No | `error = "..."`, `data = null` |
| `done` | Pipeline finished **and** the timepoint was successfully persisted to the DB | **Yes** | `data = {timepoint_id, slug, status, year, location, total_latency_ms, has_image, saved: true}` |
| `error` | Fatal failure (pipeline exception, 360s total-generation timeout, or DB save failure) | **Yes** | `error = "..."`; may include `data.timepoint_id` when the DB save specifically failed |

**Pipeline step labels and progress percentages** (order is deterministic, but `moment` and `camera` run in parallel and either may emit first):

| `step` | `progress` | Notes |
|---|---:|---|
| `initialization` | 0 | Only appears in the `start` event |
| `judge` | 10 | Query validation / rejection |
| `timeline` | 20 | Temporal anchoring |
| `scene` | 30 | Setting and atmosphere |
| `characters` | 50 | Character ID + graph + bios (all in one step) |
| `moment` | 65 | Parallel with `camera` |
| `camera` | 65 | Parallel with `moment` |
| `dialog` | 80 | Anachronism-checked dialog |
| `image_prompt` | 90 | Emitted whether or not an image is generated |
| `image_generation` | 100 | **Only emitted when `generate_image: true`** |
| `complete` | 100 | Only appears in the `done` event |
| `database_save` | 100 | Only appears on the `error` event raised when DB save fails after generation |

#### Example stream

With `generate_image: true` and a successful run:

```
data: {"event":"start","step":"initialization","data":{"query":"...","generate_image":true,"preset":"hyper"},"progress":0,"error":null}

data: {"event":"step_complete","step":"judge","data":{"latency_ms":1420,"model_used":"gemini-2.5-flash"},"progress":10,"error":null}

data: {"event":"step_complete","step":"timeline","data":{"latency_ms":2103,"model_used":"gemini-2.5-flash"},"progress":20,"error":null}

data: {"event":"step_complete","step":"scene","data":{"latency_ms":3011,"model_used":"gemini-2.5-flash"},"progress":30,"error":null}

data: {"event":"step_complete","step":"characters","data":{"latency_ms":4820,"model_used":"gemini-2.5-flash"},"progress":50,"error":null}

data: {"event":"step_complete","step":"moment","data":{"latency_ms":2910,"model_used":"gemini-2.5-flash"},"progress":65,"error":null}

data: {"event":"step_complete","step":"camera","data":{"latency_ms":2715,"model_used":"gemini-2.5-flash"},"progress":65,"error":null}

data: {"event":"step_complete","step":"dialog","data":{"latency_ms":6230,"model_used":"gemini-2.5-flash"},"progress":80,"error":null}

data: {"event":"step_complete","step":"image_prompt","data":{"latency_ms":1840,"model_used":"gemini-2.5-flash"},"progress":90,"error":null}

data: {"event":"step_complete","step":"image_generation","data":{"latency_ms":12400,"model_used":"gemini-2.5-flash-image"},"progress":100,"error":null}

data: {"event":"done","step":"complete","data":{"timepoint_id":"550e8400-e29b-41d4-a716-446655440000","slug":"oppenheimer-trinity-a1b2c3","status":"completed","year":1945,"location":"Control bunker S-10000, Jornada del Muerto, New Mexico","total_latency_ms":37473,"has_image":true,"saved":true},"progress":100,"error":null}
```

When `generate_image: false`, the `image_generation` event is omitted and `done` follows directly after `image_prompt`.

#### Client reassembly pattern

The stream only delivers **progress signals plus a reference** to the final result — the full scene body is **not** inlined in any event. Clients reassemble in four steps:

1. **Consume the SSE stream** line by line. Split on `\n\n` (SSE record delimiter) and strip the leading `data: ` prefix. Parse each record as JSON.
2. **Track progress** from `step_complete` events for UI (progress bar, per-step latency, model used).
3. **Detect completion**: the stream is finished when you receive either `event: "done"` *or* `event: "error"`. No other events terminate the stream. Always treat connection close without a terminal event as a timeout (see below).
4. **Fetch the full result** after `done` by reading `data.timepoint_id` and calling:

   ```
   GET /api/v1/timepoints/{timepoint_id}?full=true
   ```

   Pass `include_image=true` if you also need the base64 image bytes inlined. The `share_url`, characters, dialog, scene, grounding, and moment data all come from this call — not from the stream.

Minimal Python consumer:

```python
import json
import httpx

async def generate_and_fetch(query: str, base_url: str, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"query": query, "preset": "hyper", "generate_image": True}

    timepoint_id = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=180, write=10, pool=10)) as c:
        async with c.stream(
            "POST",
            f"{base_url}/api/v1/timepoints/generate/stream",
            json=payload,
            headers={**headers, "Accept": "text/event-stream"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                evt = json.loads(line[6:])
                if evt["event"] == "done":
                    timepoint_id = evt["data"]["timepoint_id"]
                    break
                if evt["event"] == "error":
                    raise RuntimeError(evt.get("error", "stream failed"))

    if not timepoint_id:
        raise RuntimeError("stream closed before done event")

    # Fetch the full result
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{base_url}/api/v1/timepoints/{timepoint_id}?full=true",
            headers=headers,
        )
        r.raise_for_status()
        return r.json()
```

Minimal curl + jq consumer (for scripts and CI):

```bash
curl -sfN -X POST "$BASE/api/v1/timepoints/generate/stream" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"Apollo 11 landing 1969","preset":"hyper"}' \
| while IFS= read -r line; do
    case "$line" in
      "data: "*)
        evt=$(printf '%s' "${line#data: }")
        event=$(jq -r '.event' <<<"$evt")
        case "$event" in
          done)
            tp_id=$(jq -r '.data.timepoint_id' <<<"$evt")
            curl -sf "$BASE/api/v1/timepoints/$tp_id?full=true" -H "Authorization: Bearer $TOKEN"
            exit 0
            ;;
          error)
            jq -r '.error' <<<"$evt" >&2
            exit 1
            ;;
        esac
        ;;
    esac
  done
```

#### Timeouts

| Layer | Timeout | Behavior on expiry |
|---|---|---|
| **Flash pipeline (server-side)** | 360s end-to-end (`asyncio.timeout(360)` in `stream_generation`) | Emits a final `{"event":"error","error":"Stream generation timed out after 360 seconds"}` then closes the stream |
| **API Gateway streaming proxy** (`api.timepointai.com`) | 120s **read timeout between bytes** — *not* a wall-clock cap | Gateway returns `504 Gateway Timeout` and closes the connection if no SSE event arrives for 120s. Because Flash emits a `step_complete` event every 5–30s, well-formed runs never hit this. |
| **Client HTTP read timeout** | Set by you | Your HTTP library will abort. Use a long per-read timeout (**≥180s recommended** when targeting `api.timepointai.com` directly, ≥360s when targeting Flash directly). |
| **Total wall-clock budget** | Preset-dependent | hyper ≈55s • balanced ≈90–110s • hd ≈120–150s • gemini3 ≈60s. Budget **≥180s** to tolerate provider fallback and retries. |

**Recommended client settings:**

| Context | Connect timeout | Read (between-events) timeout | Total timeout |
|---|---|---|---|
| Direct to Flash | 10s | 90s | 360s |
| Through API Gateway | 10s | 115s (stay under the gateway's 120s) | 300s |
| Browser `EventSource` | n/a | — (no app-level read timeout) | Rely on user cancel / tab close |

**Non-retryability.** The gateway does **not** retry streaming requests — the `/stream` proxy bypasses the normal 3× retry logic because SSE responses are not idempotent (credits are already being spent and partial events may have been delivered). If a stream fails mid-flight:

- If you received a `done` event → the timepoint is saved; `GET /api/v1/timepoints/{id}` will succeed.
- If you received a `error` event → credits were refunded for known-fatal paths (pipeline timeout / server exception); check balance before retrying.
- If the connection dropped with no terminal event → the timepoint **may or may not** have been saved. The safe recovery is to wait 10s and `GET /api/v1/users/me/timepoints?page=1&page_size=5` to look for a matching recent entry before retrying.

**Disconnect detection.** The server checks `raw_request.is_disconnected()` between each pipeline step. Closing the TCP connection within ≤5s after the next `step_complete` aborts further pipeline work and releases the worker.

---

### POST /api/v1/timepoints/generate/sync

> **Prefer `/generate/stream` for MCP tools, LLM agent loops, and any short-timeout client.** This endpoint holds a single HTTP connection open for the full pipeline run, so any intermediate proxy with a read timeout shorter than the generation budget will drop the request with no way to recover the result. Use `/generate/stream` instead — the stream's keep-alive events prevent idle-connection timeouts and the final `timepoint_id` lets you fetch the scene via `GET /api/v1/timepoints/{id}?full=true`.

Generate a scene synchronously. Blocks until complete.

**Request:** Same as streaming endpoint.

**Response:** Full `TimepointResponse` object with `preset_used`, `generation_time_ms`, and `request_context` populated.

**Timeouts and failure behavior:**

- **Server-side cap:** 300 seconds (`asyncio.wait_for`). Exceeding this returns `504 Gateway Timeout` and **refunds the credits** that were spent at request time.
- **API Gateway proxy cap:** 30 seconds read timeout on non-`/stream` paths. **This is shorter than most generation runs** and will return `504` long before Flash finishes — which is why this endpoint is not suitable for clients going through `api.timepointai.com`. Call Flash directly (`flash.timepointai.com`) with service-key auth if you must use this endpoint.
- **Pipeline exception:** Returns `500` with the exception message, refunds credits.
- **Insufficient credits:** Returns `402` before starting the pipeline.

**When this endpoint is still the right choice:**

- You are calling Flash directly (not through the Gateway) with a service key and can set a long per-request read timeout.
- You are inside a background worker where holding a 30–150s HTTP connection is acceptable.
- You need the full `TimepointResponse` in a single call and do not want to issue a follow-up `GET /timepoints/{id}`.

For every other client — especially MCP tools, gateway-fronted API consumers, and agent loops — use `/generate/stream`.

---

### POST /api/v1/timepoints/generate

Start background generation. Returns immediately with timepoint ID.

**Note:** Poll `GET /api/v1/timepoints/{id}` for completion status. Alternatively, provide a `callback_url` — Flash will POST the full result to that URL when generation completes.

**Request:** Same as streaming endpoint. Additionally supports `callback_url` and `request_context`.

When `callback_url` is provided, Flash POSTs the result on completion:
```json
{
  "timepoint": { /* full TimepointResponse */ },
  "preset_used": "balanced",
  "generation_time_ms": 95000,
  "request_context": { /* echoed back from request */ }
}
```

On failure, a minimal error payload is POSTed instead:
```json
{
  "id": "550e8400-...",
  "status": "failed",
  "error": "...",
  "request_context": { /* echoed back */ }
}
```

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Generation started for 'Oppenheimer watches the Trinity test'",
  "request_context": null
}
```

---

### GET /api/v1/timepoints/{id}

Get a completed scene.

**Query Params:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| full | boolean | false | Include full metadata (scene, characters, dialog) |
| include_image | boolean | false | Include base64 image data |

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "Oppenheimer watches the Trinity test",
  "status": "completed",
  "year": 1945,
  "month": 7,
  "day": 16,
  "season": "summer",
  "time_of_day": "pre-dawn",
  "location": "Control bunker S-10000, Jornada del Muerto, New Mexico",
  "has_image": true,
  "image_url": "https://renders.timepointai.com/timepoints/2026/04/oppenheimer-trinity-abc123/image.png",
  "text_model_used": "gemini-2.5-flash",
  "image_model_used": "gemini-2.5-flash-image",
  "visibility": "public",
  "share_url": "https://timepointai.com/t/oppenheimer-trinity-abc123",
  "characters": {
    "characters": [
      {"name": "J. Robert Oppenheimer", "role": "primary", "description": "..."},
      {"name": "Kenneth Bainbridge", "role": "secondary", "description": "..."}
    ]
  },
  "dialog": [
    {"speaker": "Bainbridge", "text": "Now we are all sons of bitches."}
  ],
  "scene": {"setting": "...", "atmosphere": "..."},
  "image_prompt": "..."
}
```

#### Response field semantics

| Field | Format | Notes |
|-------|--------|-------|
| `image_url` | Public CDN URL **or** `data:image/...;base64,...` URI | When the deployment has cloud blob storage provisioned (`BLOB_STORAGE_BACKEND=cloud` + `FLASH_BLOB_PUBLIC_BASE` set), `image_url` is a hosted URL on the CDN (e.g. `https://renders.timepointai.com/...`). Otherwise it falls back to an inline data URI containing the full base64-encoded image (multi-MB). Clients should handle both — check the prefix. See [docs/STORAGE.md](./STORAGE.md). |
| `has_image` | bool | `false` for text-only presets (`hyper`) and for failed image generations. When `false`, `image_url` is absent or empty. |
| `share_url` | URL | Pre-built public share link of the form `https://timepointai.com/t/<slug>`. Only present when (a) `SHARE_URL_BASE` is configured on the server and (b) the timepoint's visibility is `public`. Anyone with this link can view the rendered timepoint without auth. |

---

### GET /api/v1/timepoints

List scenes with pagination. Visibility filtering is applied automatically:

- **Anonymous**: sees only public timepoints.
- **Authenticated**: sees public + own private timepoints.
- **Explicit `?visibility=`**: overrides the default (private still restricted to owner).

**Query Params:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 20 | Items per page |
| status | string | null | Filter by status (completed, failed, processing) |
| visibility | string | null | Filter by visibility (`public` or `private`) |

---

### PATCH /api/v1/timepoints/{id}/visibility

Update a timepoint's visibility. Owner-only (or open when `AUTH_ENABLED=false`).

**Request:**
```json
{
  "visibility": "private"
}
```

**Response:** Full `TimepointResponse` with updated visibility.

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Invalid visibility value |
| 403 | Not the owner |
| 404 | Timepoint not found |

---

### DELETE /api/v1/timepoints/{id}

Delete a scene.

---

## Character Interactions

### POST /api/v1/interactions/{id}/chat

Chat with a character from a scene.

**Request:**
```json
{
  "character": "Benjamin Franklin",
  "message": "What do you think of this document?"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| character | string | Yes | Character name (case-insensitive) |
| message | string | Yes | Your message |
| session_id | string | No | Continue existing conversation |

**Response:**
```json
{
  "character_name": "Benjamin Franklin",
  "response": "My dear friend, this document represents our highest aspirations...",
  "emotional_tone": "thoughtful",
  "session_id": "sess_123"
}
```

---

### POST /api/v1/interactions/{id}/chat/stream

Same as above, but streams the response token-by-token.

---

### POST /api/v1/interactions/{id}/dialog

Generate more dialog between characters.

**Request:**
```json
{
  "num_lines": 5,
  "prompt": "They discuss the risks of signing"
}
```

---

### POST /api/v1/interactions/{id}/survey

Ask all characters the same question.

**Request:**
```json
{
  "questions": ["What do you fear most about this moment?"],
  "include_summary": true
}
```

**Response:**
```json
{
  "responses": [
    {
      "character_name": "John Adams",
      "response": "That we shall all hang for this...",
      "sentiment": "negative",
      "emotional_tone": "anxious"
    }
  ],
  "summary": "The founders express a mixture of fear and determination..."
}
```

---

## Time Travel

### POST /api/v1/temporal/{id}/next

Generate a scene at a later point in time, preserving characters and context.

**Request:**
```json
{
  "units": 1,
  "unit": "hour"
}
```

| Field | Type | Default | Options |
|-------|------|---------|---------|
| units | int | 1 | 1-365 |
| unit | string | "day" | second, minute, hour, day, week, month, year |

**Response:**
```json
{
  "source_id": "550e8400-...",
  "target_id": "661f9511-...",
  "source_year": 1969,
  "target_year": 1969,
  "direction": "next",
  "units": 1,
  "unit": "hour",
  "message": "Generated moment 1 hour(s) forward"
}
```

Use `GET /api/v1/timepoints/{target_id}?full=true` to retrieve the generated scene.

---

### POST /api/v1/temporal/{id}/prior

Same as above, but backward in time. Response has `"direction": "prior"`.

---

### GET /api/v1/temporal/{id}/sequence

Get all linked scenes (prior and next). When a timepoint has multiple children from separate time-jumps, the most recently created child is followed.

**Query Params:**
| Name | Default | Options |
|------|---------|---------|
| direction | "both" | prior, next, both |
| limit | 10 | 1-50 |

**Response:**
```json
{
  "center": {"id": "...", "year": 1776, "slug": "declaration-signing-abc123"},
  "prior": [],
  "next": [
    {"id": "...", "year": 1776, "slug": "one-hour-after-declaration-def456"}
  ]
}
```

---

## Models

### GET /api/v1/models

List available AI models.

**Query Params:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| fetch_remote | boolean | false | Fetch live models from OpenRouter |
| free_only | boolean | false | Only return free models |

### GET /api/v1/models/free

Get available free models from OpenRouter. The `best` and `fastest` picks are auto-selected.

**Response:**
```json
{
  "best": {
    "id": "qwen/qwen3-next-80b-a3b-instruct:free",
    "name": "Qwen3 Next 80B (free)",
    "context_length": 40960,
    "is_free": true
  },
  "fastest": {
    "id": "liquid/lfm-2.5-1.2b-thinking:free",
    "name": "LFM 2.5 1.2B Thinking (free)",
    "context_length": 32768,
    "is_free": true
  },
  "all_free": [...],
  "total": 30
}
```

Note: Free model availability changes frequently on OpenRouter. The `best`/`fastest` picks are determined dynamically.

### GET /api/v1/models/providers

Check which providers (Google, OpenRouter) are configured and their model counts.

**Response:**
```json
{
  "providers": [
    {
      "provider": "google",
      "available": true,
      "models_count": 3,
      "default_text_model": "gemini-2.5-flash",
      "default_image_model": "gemini-2.5-flash-image"
    },
    {
      "provider": "openrouter",
      "available": true,
      "models_count": 300,
      "default_text_model": "anthropic/claude-3.5-sonnet",
      "default_image_model": "gemini-2.5-flash-image"
    }
  ]
}
```

---

## Evaluation

Compare model latency and performance across providers.

### POST /api/v1/eval/compare

Run the same prompt across multiple models in parallel. Returns raw JSON results.

**Request:**
```json
{
  "query": "Kasparov Deep Blue Game 6 1997",
  "preset": "verified"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | Prompt to send to all models |
| preset | string | No | Model set: `verified` (default), `google_native`, `openrouter`, `all` |
| models | array | No | Specific model configs (alternative to preset) |
| prompt_type | string | No | Prompt type label (default: `text`) |
| timeout_seconds | int | No | Max time per model, 10-600 (default: 120) |

**Response:**
```json
{
  "query": "Kasparov Deep Blue Game 6 1997",
  "prompt_type": "text",
  "timestamp": "2026-02-05T10:47:29Z",
  "total_duration_ms": 16045,
  "models_tested": 4,
  "fastest_model": "google/gemini-3-flash-preview",
  "slowest_model": "gemini-2.5-flash",
  "success_count": 4,
  "failure_count": 0,
  "success_rate": 100.0,
  "latency_stats": {
    "min_ms": 6453,
    "max_ms": 15890,
    "avg_ms": 10150,
    "median_ms": 9240,
    "range_ms": 9437
  },
  "ranking": [
    "google/gemini-3-flash-preview",
    "google/gemini-2.0-flash-001",
    "gemini-2.5-flash",
    "gemini-2.5-flash-thinking"
  ],
  "results": [
    {
      "model_id": "google/gemini-3-flash-preview",
      "provider": "openrouter",
      "label": "Gemini 3 Flash Preview",
      "success": true,
      "latency_ms": 6453,
      "output_length": 2847,
      "output_preview": "This is a valid historical query..."
    }
  ]
}
```

---

### POST /api/v1/eval/compare/report

Same as `/compare`, but returns both JSON data and a formatted ASCII report.

**Request:** Same as `/compare`.

**Response:**
```json
{
  "comparison": { ... },
  "report": "╔══════════════════════════════════════╗\n║   MODEL COMPARISON RESULTS          ║\n..."
}
```

The `report` field contains a human-readable table with rankings, latencies, and success/failure indicators. Useful for CLI display or logging.

---

### GET /api/v1/eval/models

List available models and presets for evaluation.

**Response:**
```json
{
  "presets": {
    "verified": 4,
    "google_native": 2,
    "openrouter": 2,
    "all": 4
  },
  "models": [
    {
      "model_id": "gemini-2.5-flash",
      "provider": "google",
      "label": "Gemini 2.5 Flash"
    },
    {
      "model_id": "google/gemini-3-flash-preview",
      "provider": "openrouter",
      "label": "Gemini 3 Flash Preview"
    }
  ]
}
```

---

## Service-to-Service Auth

Flash supports three auth mechanisms for service and user traffic.

### Signed Gateway requests (preferred, API-4)

When `GATEWAY_SIGNING_SECRET` is set, every request from the API Gateway is
HMAC-SHA256 signed with two extra headers:

* `X-Gateway-Timestamp` — unix epoch seconds
* `X-Gateway-Signature` — `v1=<hex>` HMAC-SHA256 over the canonical string
  `v1\n{METHOD}\n{PATH}\n{X-User-Id}\n{timestamp}`

The signature binds `X-User-Id` to the request, so an attacker who only holds
the legacy `X-Service-Key` cannot impersonate arbitrary users. Timestamps
must be within ±300 seconds of Flash's clock.

Set `REQUIRE_SIGNED_GATEWAY=true` once all callers are signing to reject any
non-health traffic that lacks a valid signature.

### Legacy shared-secret (system calls, transitional)

**Header:** `X-Service-Key: {FLASH_SERVICE_KEY}`

`get_current_user` evaluates these paths in order:

| Priority | Headers | Behavior | Use Case |
|----------|---------|----------|----------|
| 1 | Valid `X-Gateway-Signature` (+ `X-User-Id`) | Signature verifies, user trusted | Gateway forwards an authenticated user |
| 2 | Valid `X-Gateway-Signature`, no `X-User-Id` | System call from Gateway, no user context | Gateway internal endpoints (image fetch, spend, etc.) |
| 3 | `X-Service-Key` only (no signature) | System call — **`X-User-Id` is IGNORED** if set | Clockchain / Billing / MCP calling Flash directly (no user identity) |
| 4 | `Authorization: Bearer <JWT>` | Validates JWT, returns authenticated user | Direct iOS auth |

Path 3 is the critical change from pre-API-4 behavior: a leaked
`X-Service-Key` can no longer be combined with an arbitrary `X-User-Id` to
impersonate a user. Set `ALLOW_LEGACY_SERVICE_KEY=false` once all system
callers have migrated to signed requests to close this path entirely.

When `AUTH_ENABLED=false` and no service key is provided, all endpoints are open-access.

**Admin operations** (credit grants, dev tokens) use a separate `X-Admin-Key` header matching `ADMIN_API_KEY`.

---

## Authentication

Auth endpoints are always available but only functional when `AUTH_ENABLED=true`.

### POST /api/v1/auth/dev/token (Admin)

Create a test user (or find existing by email) and return a JWT pair. Requires `X-Admin-Key` header matching the `ADMIN_API_KEY` env var. Returns 403 if the key is missing, wrong, or `ADMIN_API_KEY` is not set.

On first creation, the user gets signup credits (default 50).

**Request:**
```json
{
  "email": "test@example.com",
  "display_name": "Test User"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| email | string | Yes | Email for the test user |
| display_name | string | No | Optional display name |

**Headers:**
```
X-Admin-Key: your-admin-key
```

**Response:** Same shape as `/auth/apple`.

---

### POST /api/v1/auth/apple

Verify an Apple identity token and return a JWT pair. Creates a new user on first sign-in and grants signup credits.

**Request:**
```json
{
  "identity_token": "eyJhbGciOiJSUzI1NiIs..."
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "abc123...",
  "token_type": "bearer",
  "expires_in": 900
}
```

---

### POST /api/v1/auth/refresh

Rotate a refresh token and return a new JWT pair. The old refresh token is revoked.

**Request:**
```json
{
  "refresh_token": "abc123..."
}
```

**Response:** Same shape as `/auth/apple`.

---

### GET /api/v1/auth/me

Return the current user's profile. Requires Bearer JWT.

**Response:**
```json
{
  "id": "550e8400-...",
  "email": "user@example.com",
  "display_name": null,
  "created_at": "2026-02-09T12:00:00Z"
}
```

---

### POST /api/v1/auth/logout

Revoke a refresh token. Always returns 200.

**Request:**
```json
{
  "refresh_token": "abc123..."
}
```

**Response:**
```json
{
  "detail": "Logged out"
}
```

---

### DELETE /api/v1/auth/account

Soft-delete user account. Sets `is_active=false` and revokes all refresh tokens. Required for App Store compliance. Requires Bearer JWT.

**Response:**
```json
{
  "detail": "Account deactivated"
}
```

---

## Credits

### GET /api/v1/credits/balance

Current credit balance. Requires Bearer JWT.

**Response:**
```json
{
  "balance": 45,
  "lifetime_earned": 50,
  "lifetime_spent": 5
}
```

---

### GET /api/v1/credits/history

Paginated transaction ledger. Requires Bearer JWT.

**Query Params:**
| Name | Type | Default |
|------|------|---------|
| limit | int | 20 |
| offset | int | 0 |

**Response:**
```json
[
  {
    "amount": -5,
    "balance_after": 45,
    "type": "generation",
    "description": "Scene generation (balanced)",
    "created_at": "2026-02-09T12:00:00Z"
  }
]
```

---

### POST /api/v1/credits/admin/grant (Admin)

Grant credits to any user by user ID. Requires `X-Admin-Key` header matching the `ADMIN_API_KEY` env var. Returns 403 if the key is missing, wrong, or `ADMIN_API_KEY` is not set.

**Request:**
```json
{
  "user_id": "550e8400-...",
  "amount": 100,
  "transaction_type": "stripe_purchase",
  "description": "Stripe purchase: 100 credits ($9.99)"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| user_id | string | Yes | Target user UUID |
| amount | int | Yes | Credits to grant (must be > 0) |
| transaction_type | string | No | Ledger transaction type (default: `admin_grant`). Valid: `admin_grant`, `apple_iap`, `stripe_purchase`, `subscription_grant`, `refund`, `signup_bonus` |
| description | string | No | Ledger note (default: "Manual top-up") |

**Headers:**
```
X-Admin-Key: your-admin-key
```

**Response:**
```json
{
  "balance": 150,
  "granted": 100
}
```

---

### GET /api/v1/credits/costs

Credit cost table. No auth required.

**Response:**
```json
{
  "costs": {
    "generate_balanced": 5,
    "generate_hd": 10,
    "generate_hyper": 5,
    "generate_gemini3": 5,
    "chat": 1,
    "temporal_jump": 2
  }
}
```

---

## Users

### GET /api/v1/users/me/timepoints

Paginated list of the authenticated user's timepoints. Requires Bearer JWT.

**Query Params:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| page | int | 1 | Page number |
| page_size | int | 20 | Items per page (max 100) |
| status | string | null | Filter by status (completed, failed, processing) |

**Response:**
```json
{
  "items": [
    {
      "id": "550e8400-...",
      "query": "Oppenheimer Trinity test 1945",
      "slug": "oppenheimer-trinity-test-a1b2c3",
      "status": "completed",
      "year": 1945,
      "location": "Jornada del Muerto, New Mexico",
      "has_image": true,
      "created_at": "2026-02-09T12:00:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### POST /api/v1/users/resolve

Find or create a user by `external_id` (Auth0 sub or other external identity provider ID). Service-key protected — requires `X-Service-Key` header matching `FLASH_SERVICE_KEY`.

**Headers:**
```
X-Service-Key: your-flash-service-key
```

**Request:**
```json
{
  "external_id": "auth0|abc123",
  "email": "user@example.com",
  "display_name": "Jane Doe"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| external_id | string | Yes | Auth0 sub or other external provider ID |
| email | string | No | User email (set on create only) |
| display_name | string | No | Display name (set on create only) |

**Response:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "created": true
}
```

| Status | Meaning |
|--------|---------|
| 200 | User found or created |
| 403 | Invalid service key |
| 503 | `FLASH_SERVICE_KEY` not configured |

---

### GET /api/v1/users/me/export

Full JSON export of user data for GDPR Subject Access Request compliance. Returns profile, complete credit history, and full scene JSON for every user timepoint. Requires Bearer JWT.

**Response:**
```json
{
  "user": {
    "id": "550e8400-...",
    "email": "user@example.com",
    "display_name": null,
    "created_at": "2026-02-09T12:00:00Z",
    "last_login_at": "2026-02-09T12:00:00Z",
    "is_active": true
  },
  "credit_history": [...],
  "timepoints": [...]
}
```

---

## Health

### GET /health

```json
{
  "status": "healthy",
  "version": "2.4.0",
  "database": true,
  "providers": {
    "google": true,
    "openrouter": true
  }
}
```

---

## Provider Resilience

TIMEPOINT Flash uses a dual-provider architecture with automatic failover:

**Primary:** Google Gemini (native API)
**Fallback:** OpenRouter (300+ models)

### Automatic Fallback

When Google API quota is exhausted or rate-limited:
1. **Quota exhaustion** (daily limit = 0) - Immediate fallback, no retries
2. **Rate limiting** (temporary) - Retry with exponential backoff, then fallback

### Error Types

| Error | Retries | Action |
|-------|---------|--------|
| `QuotaExhaustedError` | 0 | Instant fallback to OpenRouter |
| `RateLimitError` | Up to 3 | Exponential backoff, then fallback |
| `AuthenticationError` | 0 | Fail with 401 |
| `ProviderError` | Up to 3 | Retry, then fallback |

### Image Generation

Image generation uses a 2-tier fallback chain:

| Priority | Provider | Details |
|----------|----------|---------|
| 1 | **Google Imagen** | Native API, highest quality. Quota exhaustion = instant fallback. |
| 2 | **OpenRouter** | Via `/chat/completions` with `modalities: ["image", "text"]`. Best available model auto-selected. |

**Behavior:**
- Quota exhaustion on Google = immediate fallback to OpenRouter (no retries wasted)
- In permissive mode, images route directly to OpenRouter (Google-free)
- Scene completes with image from whichever provider succeeds

---

## Errors

All errors return:
```json
{"detail": "Error message"}
```

| Code | Meaning |
|------|---------|
| 400 | Invalid request state |
| 401 | Unauthorized — missing/invalid/expired JWT (when `AUTH_ENABLED=true`) |
| 402 | Payment Required — insufficient credits for the operation |
| 403 | Forbidden — private timepoint and requester is not the owner |
| 404 | Not found |
| 422 | Validation error |
| 429 | Rate limit exceeded (triggers fallback internally) |
| 500 | Server error |

Rate limit: 60 requests/minute per IP.

---

## Known Issues

1. **No API `preset: "free"` option** - The API does not have a built-in "free" preset. However, free models ARE fully supported:
   - **CLI**: `demo.sh` has built-in free model selection (preset options 5/6) and "RAPID TEST FREE" menu option
   - **API**: Use `text_model` override with free model IDs from `/api/v1/models/free` (e.g., `google/gemini-2.0-flash-001:free`)

---

*Last updated: 2026-04-24*
