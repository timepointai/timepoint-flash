# API Reference

Base URL: `http://localhost:8000`

Interactive docs: [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)

---

## Quick Examples

**Generate a scene (streaming - recommended):**
```bash
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "moon landing 1969", "preset": "hyper", "generate_image": true}'
```

**Chat with a character:**
```bash
curl -X POST http://localhost:8000/api/v1/interactions/{timepoint_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character": "Neil Armstrong", "message": "What did it feel like to step on the moon?"}'
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
| **hyper** | ~50s | Good | `google/gemini-2.0-flash-001` | OpenRouter |
| **balanced** | ~90s | Better | `gemini-2.5-flash` | Google Native |
| **hd** | ~120s | Best | `gemini-2.5-flash` (extended thinking) | Google Native |
| **gemini3** | ~45s | Excellent | `google/gemini-3-flash-preview` | OpenRouter |

**Usage:**
```json
{
  "query": "boston tea party",
  "preset": "hyper",
  "generate_image": false
}
```

**Model Overrides:**

Override preset models for custom configurations:
```json
{
  "query": "boston tea party",
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
| **Get** | `GET /api/v1/timepoints/{id}` | Retrieve a scene |
| **Chat** | `POST /api/v1/interactions/{id}/chat` | Talk to a character |
| **Time Travel** | `POST /api/v1/temporal/{id}/next` | Jump forward |
| **Time Travel** | `POST /api/v1/temporal/{id}/prior` | Jump backward |
| **Models** | `GET /api/v1/models/free` | List free OpenRouter models |

---

## Timepoints

### POST /api/v1/timepoints/generate/stream (Recommended)

Generate a scene with real-time progress updates via Server-Sent Events.

**Request:**
```json
{
  "query": "signing of the declaration of independence",
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
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "abc123", "slug": "...", "status": "completed"}}
```

---

### POST /api/v1/timepoints/generate/sync

Generate a scene synchronously. Blocks until complete (30-120 seconds).

**Request:** Same as streaming endpoint.

**Response:** Full `TimepointResponse` object.

---

### POST /api/v1/timepoints/generate

Start background generation. Returns immediately with timepoint ID.

**Note:** Poll `GET /api/v1/timepoints/{id}` for completion status.

**Request:** Same as streaming endpoint (preset support limited - see Known Issues).

**Response:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Generation started for 'moon landing 1969'"
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
  "query": "signing of the declaration",
  "status": "completed",
  "year": 1776,
  "month": 7,
  "day": 4,
  "season": "summer",
  "time_of_day": "afternoon",
  "location": "Independence Hall, Philadelphia",
  "characters": {
    "characters": [
      {"name": "John Hancock", "role": "primary", "description": "..."},
      {"name": "Benjamin Franklin", "role": "secondary", "description": "..."}
    ]
  },
  "dialog": [
    {"speaker": "John Hancock", "text": "Let us sign this declaration..."}
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

---

### POST /api/v1/temporal/{id}/prior

Same as above, but backward in time.

---

### GET /api/v1/temporal/{id}/sequence

Get all linked scenes (prior and next).

**Query Params:**
| Name | Default | Options |
|------|---------|---------|
| direction | "both" | prior, next, both |
| limit | 10 | 1-50 |

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

Get available free models from OpenRouter.

**Response:**
```json
{
  "best": {
    "id": "google/gemini-2.0-flash-exp:free",
    "name": "Google: Gemini 2.0 Flash Experimental (free)",
    "context_length": 1048576,
    "is_free": true
  },
  "fastest": {
    "id": "google/gemini-2.0-flash-exp:free",
    "name": "Google: Gemini 2.0 Flash Experimental (free)",
    "context_length": 1048576,
    "is_free": true
  },
  "all_free": [...],
  "total": 15
}
```

### GET /api/v1/models/providers

Check which providers (Google, OpenRouter) are configured.

**Response:**
```json
{
  "google": true,
  "openrouter": true
}
```

---

## Health

### GET /health

```json
{
  "status": "healthy",
  "version": "2.2.1",
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

1. **`POST /generate` ignores preset parameter** - The background generation endpoint does not pass the preset to the pipeline. Use `/generate/stream` or `/generate/sync` instead.

2. **No API `preset: "free"` option** - The API does not have a built-in "free" preset. However, free models ARE fully supported:
   - **CLI**: `demo.sh` has built-in free model selection (preset options 5/6) and "RAPID TEST FREE" menu option
   - **API**: Use `text_model` override with free model IDs from `/api/v1/models/free` (e.g., `google/gemini-2.0-flash-001:free`)

---

*Last updated: 2026-01-05*
