# Using TIMEPOINT Flash — Agent Quick Start

You're an AI agent with access to a running TIMEPOINT Flash server. This guide shows you how to use it.

**Base URL:** `https://timepoint-flash-deploy-production.up.railway.app`

No authentication is required (AUTH_ENABLED=false). All endpoints are open-access.

---

## 1. Check the Server

```bash
curl https://timepoint-flash-deploy-production.up.railway.app/health
```

Expected:
```json
{"status": "healthy", "version": "2.4.0", "database": true, "providers": {"google": true, "openrouter": true}}
```

If `status` is `"degraded"`, the database is down. If a provider shows `false`, that provider's API key is missing — scenes will still generate via the other provider.

---

## 2. Generate a Scene

The core operation. Give it a historical moment, get back characters, dialog, relationships, and optionally a photorealistic image.

### Synchronous (simplest)

```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/timepoints/generate/sync \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Alan Turing breaks Enigma at Bletchley Park Hut 8, winter 1941",
    "preset": "balanced",
    "generate_image": true
  }'
```

This blocks for 30-120 seconds and returns the complete scene.

### Streaming (recommended for UIs)

```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Oppenheimer watches the Trinity test, 5:29 AM July 16 1945",
    "preset": "hyper",
    "generate_image": true
  }'
```

Returns Server-Sent Events with progress updates:
```
data: {"event": "step_complete", "step": "judge", "progress": 10}
data: {"event": "step_complete", "step": "timeline", "progress": 20}
...
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "abc123", ...}}
```

### Background (fire and forget)

```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/timepoints/generate \
  -H "Content-Type: application/json" \
  -d '{"query": "Gavrilo Princip at Schiller Deli Sarajevo June 28 1914", "preset": "balanced"}'
```

Returns immediately with a timepoint ID. Poll `GET /api/v1/timepoints/{id}` until `status` is `"completed"`.

### Request Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Historical moment description (3-500 chars) |
| `preset` | string | No | `"balanced"` | Quality preset (see below) |
| `generate_image` | bool | No | `false` | Generate a photorealistic image |
| `visibility` | string | No | `"public"` | `"public"` or `"private"` — controls who can see full data |
| `text_model` | string | No | — | Override text model (ignores preset) |
| `image_model` | string | No | — | Override image model (ignores preset) |

### Quality Presets

| Preset | Speed | Best For |
|--------|-------|----------|
| `hyper` | ~55s | Fast iteration, prototyping |
| `balanced` | ~90-110s | Production quality (default) |
| `hd` | ~2-2.5 min | Maximum fidelity (extended thinking) |
| `gemini3` | ~60s | Latest model, best quality/speed ratio |

---

## 3. Retrieve a Scene

```bash
curl "https://timepoint-flash-deploy-production.up.railway.app/api/v1/timepoints/{id}?full=true&include_image=true"
```

- `full=true` — include scene, characters, dialog, relationships
- `include_image=true` — include base64 image data

### What You Get Back

A scene contains:

| Field | Description |
|-------|-------------|
| `query` | Original input |
| `year`, `month`, `day`, `season`, `time_of_day` | Extracted temporal data |
| `location` | Verified location (Google Search grounded) |
| `scene` | Setting description, atmosphere, mood |
| `characters` | Up to 6 people with names, roles, bios, voice styles |
| `dialog` | Up to 7 voice-differentiated lines |
| `image_prompt` | The prompt used for image generation |
| `has_image` / `image_url` | Whether an image was generated and its base64 data |
| `text_model_used` / `image_model_used` | Which models were actually used |
| `visibility` | `"public"` or `"private"` |
| `share_url` | Shareable link (only for public scenes when `SHARE_URL_BASE` is configured) |

---

## 4. Talk to Characters

When `AUTH_ENABLED=true`, interaction endpoints require a Bearer JWT and deduct credits. Private timepoints block interactions for non-owners (403).

After generating a scene, chat with any character in it:

```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/interactions/{timepoint_id}/chat \
  -H "Content-Type: application/json" \
  -d '{
    "character": "Oppenheimer",
    "message": "What did you feel when the sky turned white?"
  }'
```

Response:
```json
{
  "character_name": "J. Robert Oppenheimer",
  "response": "There are no words for it. A light that is not light...",
  "emotional_tone": "haunted",
  "session_id": "sess_abc123"
}
```

Pass `session_id` back in subsequent requests to continue the conversation.

### Other Interaction Endpoints

**Generate more dialog:**
```bash
POST /api/v1/interactions/{id}/dialog
{"num_lines": 5, "prompt": "They discuss the implications"}
```

**Survey all characters (same question to everyone):**
```bash
POST /api/v1/interactions/{id}/survey
{"questions": ["What do you fear most about this moment?"], "include_summary": true}
```

---

## 5. Time Travel

Jump forward or backward from any scene. The new scene preserves characters and context.

**Jump forward:**
```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/temporal/{timepoint_id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "hour"}'
```

**Jump backward:**
```bash
curl -X POST https://timepoint-flash-deploy-production.up.railway.app/api/v1/temporal/{timepoint_id}/prior \
  -H "Content-Type: application/json" \
  -d '{"units": 30, "unit": "minute"}'
```

Unit options: `second`, `minute`, `hour`, `day`, `week`, `month`, `year`

The response gives you a `target_id` — retrieve the generated scene with `GET /api/v1/timepoints/{target_id}?full=true`.

**Get the full timeline:**
```bash
GET /api/v1/temporal/{id}/sequence?direction=both&limit=10
```

---

## 6. List and Browse Scenes

```bash
# List all scenes (paginated)
GET /api/v1/timepoints?page=1&page_size=20&status=completed

# Filter by visibility
GET /api/v1/timepoints?visibility=public
GET /api/v1/timepoints?visibility=private   # owner only (requires auth)

# Set a scene to private
curl -X PATCH https://timepoint-flash-deploy-production.up.railway.app/api/v1/timepoints/{id}/visibility \
  -H "Content-Type: application/json" \
  -d '{"visibility": "private"}'

# Delete a scene
DELETE /api/v1/timepoints/{id}
```

**Visibility rules:**
- **Anonymous**: sees only public timepoints
- **Authenticated**: sees public + own private timepoints
- **Private non-owner**: gets 403 on `GET /{id}`, interactions, and time travel

---

## 7. Model Info

```bash
# Available providers and their status
GET /api/v1/models/providers

# Free models available on OpenRouter
GET /api/v1/models/free

# Compare model latencies
POST /api/v1/eval/compare
{"query": "Kasparov Deep Blue Game 6 1997", "preset": "verified"}
```

---

## Tips for AI Agents

1. **Use `preset: "hyper"` for fast iteration** — 55 seconds vs 2+ minutes for HD.
2. **Skip image generation unless needed** — `generate_image: false` (default) cuts time significantly.
3. **Use sync endpoint for simplicity** — streaming is only useful if you're updating a UI.
4. **Queries work best with specifics** — include who, where, and when. "Oppenheimer Trinity test 5:29 AM July 16 1945" beats "Oppenheimer nuclear bomb."
5. **Characters are interactive** — after generating a scene, you can chat with anyone in it, ask follow-up questions, or extend the dialog.
6. **Time travel chains scenes** — jump forward/backward to build a narrative sequence from a single starting point.
7. **Free models exist** — check `GET /api/v1/models/free` and pass the model ID as `text_model` override to use free OpenRouter models.

---

## Error Handling

| Code | Meaning |
|------|---------|
| 400 | Invalid request (bad query, invalid preset) |
| 401 | Unauthorized — missing/invalid JWT (when `AUTH_ENABLED=true`) |
| 402 | Payment Required — insufficient credits |
| 403 | Forbidden — private timepoint, not the owner |
| 404 | Timepoint not found |
| 422 | Validation error (check request body) |
| 429 | Rate limited (60 req/min per IP) |
| 500 | Server error |

All errors return `{"detail": "Error message"}`.

---

## Full API Reference

For complete endpoint documentation including auth, credits, and eval: [API.md](API.md)

OpenAPI schema available at: `https://timepoint-flash-deploy-production.up.railway.app/openapi.json`

---

*Last updated: 2026-02-16*
