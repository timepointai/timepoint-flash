# API Reference

Base URL: `http://localhost:8000`

Interactive docs: [Swagger UI](http://localhost:8000/docs) | [ReDoc](http://localhost:8000/redoc)

---

## Quick Examples

**Generate a scene:**
```bash
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "moon landing 1969", "generate_image": true}'
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

## Endpoints Overview

| Category | Endpoint | Description |
|----------|----------|-------------|
| **Generate** | `POST /api/v1/timepoints/generate/stream` | Create a scene (streaming) |
| **Get** | `GET /api/v1/timepoints/{id}` | Retrieve a scene |
| **Chat** | `POST /api/v1/interactions/{id}/chat` | Talk to a character |
| **Time Travel** | `POST /api/v1/temporal/{id}/next` | Jump forward |
| **Time Travel** | `POST /api/v1/temporal/{id}/prior` | Jump backward |

---

## Timepoints

### POST /api/v1/timepoints/generate/stream

Generate a scene with real-time progress updates via Server-Sent Events.

**Request:**
```json
{
  "query": "signing of the declaration of independence",
  "generate_image": true
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | Historical moment (3-500 chars) |
| generate_image | boolean | No | Generate AI image (default: false) |

**Response:** SSE stream with events:

```
data: {"event": "start", "step": "initialization", "progress": 0}
data: {"event": "step_complete", "step": "judge", "progress": 10}
data: {"event": "step_complete", "step": "timeline", "progress": 20}
data: {"event": "step_complete", "step": "scene", "progress": 30}
data: {"event": "step_complete", "step": "characters", "progress": 40}
data: {"event": "step_complete", "step": "dialog", "progress": 60}
data: {"event": "step_complete", "step": "image_prompt", "progress": 90}
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "abc123"}}
```

---

### GET /api/v1/timepoints/{id}

Get a completed scene.

**Query Params:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
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
      {"name": "John Hancock", "role": "President of Congress", "bio": "..."},
      {"name": "Benjamin Franklin", "role": "Elder statesman", "bio": "..."}
    ]
  },
  "dialog": [
    {"speaker": "John Hancock", "line": "Let us sign this declaration..."}
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

### GET /api/v1/models/providers

Check which providers (Google, OpenRouter) are configured.

---

## Health

### GET /health

```json
{"status": "healthy", "version": "2.2.1"}
```

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
| 429 | Rate limit exceeded |
| 500 | Server error |

Rate limit: 60 requests/minute per IP.
