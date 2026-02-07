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

---

## Endpoints Overview

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Generate** | `POST /api/v1/timepoints/generate/stream` | Create a scene (streaming) - **recommended** |
| **Generate** | `POST /api/v1/timepoints/generate/sync` | Create a scene (blocking) |
| **Generate** | `POST /api/v1/timepoints/generate` | Create a scene (background task) |

All generation endpoints run a 14-agent pipeline with critique loop: dialog is reviewed for anachronisms, cultural errors, and voice distinctiveness, and retried if critical issues are found. Characters are capped at 6 with social register-based voice differentiation. Image prompts translate narrative emotion into physicalized body language (~77 words).
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

Generate a scene with real-time progress updates via Server-Sent Events.

**Request:**
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
| text_model | string | No | Override text model (ignores preset) |
| image_model | string | No | Override image model (ignores preset) |

**Response:** SSE stream with events:

```
data: {"event": "start", "step": "initialization", "progress": 0}
data: {"event": "step_complete", "step": "judge", "progress": 10}
data: {"event": "step_complete", "step": "timeline", "progress": 20}
data: {"event": "step_complete", "step": "scene", "progress": 30}
data: {"event": "step_complete", "step": "characters", "progress": 50}
data: {"event": "step_complete", "step": "moment", "progress": 65}
data: {"event": "step_complete", "step": "camera", "progress": 65}
data: {"event": "step_complete", "step": "dialog", "progress": 80}
data: {"event": "step_complete", "step": "image_prompt", "progress": 90}
data: {"event": "step_complete", "step": "image_generation", "progress": 100}
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "abc123", "slug": "...", "status": "completed"}}
```

Note: The `image_generation` step only appears when `generate_image: true`. Without it, `done` follows `image_prompt` directly.

---

### POST /api/v1/timepoints/generate/sync

Generate a scene synchronously. Blocks until complete (30-120 seconds).

**Request:** Same as streaming endpoint.

**Response:** Full `TimepointResponse` object.

---

### POST /api/v1/timepoints/generate

Start background generation. Returns immediately with timepoint ID.

**Note:** Poll `GET /api/v1/timepoints/{id}` for completion status.

**Request:** Same as streaming endpoint.

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Generation started for 'Oppenheimer watches the Trinity test'"
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
  "image_url": "data:image/jpeg;base64,...",
  "text_model_used": "gemini-2.5-flash",
  "image_model_used": "gemini-2.5-flash-image",
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

---

### GET /api/v1/timepoints

List all scenes with pagination.

**Query Params:**
| Name | Type | Default |
|------|------|---------|
| page | int | 1 |
| page_size | int | 20 |
| status | string | null | Filter by status (completed, failed, processing) |

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

## Health

### GET /health

```json
{
  "status": "healthy",
  "version": "2.3.3",
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

Image generation uses a resilient 3-tier fallback chain:

| Priority | Provider | Details |
|----------|----------|---------|
| 1 | **Google Imagen** | Native API, highest quality. Quota exhaustion = instant fallback. |
| 2 | **OpenRouter Flux** | Via `/chat/completions` with `modalities: ["image", "text"]` |
| 3 | **Pollinations.ai** | Free, no API key required. Ultimate fallback, never fails. |

**Behavior:**
- Quota exhaustion on Google = immediate fallback (no retries wasted)
- OpenRouter failure = fallback to Pollinations.ai
- Pollinations.ai = always succeeds (free API, no rate limits)
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

*Last updated: 2026-02-07*
