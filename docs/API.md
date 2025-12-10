# TIMEPOINT Flash API Reference

Complete API documentation for TIMEPOINT Flash v2.2.1.

**Interactive docs**: http://localhost:8000/docs (Swagger) | http://localhost:8000/redoc (ReDoc)

Base URL: `http://localhost:8000`

---

## Health Endpoints

### GET /health

Root health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.2.1"
}
```

### GET /api/v1/health

API health check with database status.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected"
}
```

---

## Timepoints API

### POST /api/v1/timepoints/generate

Generate a new timepoint from a natural language query.

**Request Body:**
```json
{
  "query": "signing of the declaration of independence"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| query | string | Yes | Natural language temporal query (3-500 chars) |

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Generation started"
}
```

**Errors:**
- 422: Validation error (query too short/long)

---

### POST /api/v1/timepoints/generate/stream

Generate a timepoint with real-time SSE progress events. Events are emitted **immediately after each pipeline step completes**, providing true real-time progress updates.

**Request Body:**
```json
{
  "query": "rome 50 BCE",
  "generate_image": false
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| query | string | Yes | - | Natural language temporal query |
| generate_image | boolean | No | false | Whether to generate image (adds image_gen step) |

**Response:** Server-Sent Events (text/event-stream)

**Streaming Behavior:**
- Each event is sent **as soon as** the corresponding pipeline step finishes
- Progress percentages indicate approximate completion (not wall-clock time)
- The pipeline uses an async generator to yield results after each step
- If `generate_image=true`, an additional `image_gen` step runs at 95%

**Event Types:**

```
data: {"event": "start", "step": "initialization", "progress": 0, "data": {"query": "..."}}

data: {"event": "step_complete", "step": "judge", "progress": 10, "data": {"latency_ms": 150}}

data: {"event": "step_complete", "step": "timeline", "progress": 20, "data": {...}}

data: {"event": "step_complete", "step": "scene", "progress": 30, "data": {...}}

data: {"event": "step_complete", "step": "characters", "progress": 40, "data": {...}}

data: {"event": "step_complete", "step": "moment", "progress": 50, "data": {...}}

data: {"event": "step_complete", "step": "dialog", "progress": 60, "data": {...}}

data: {"event": "step_complete", "step": "camera", "progress": 70, "data": {...}}

data: {"event": "step_complete", "step": "graph", "progress": 80, "data": {...}}

data: {"event": "step_complete", "step": "image_prompt", "progress": 90, "data": {...}}

data: {"event": "step_complete", "step": "image_gen", "progress": 95, "data": {...}}  // if generate_image=true

data: {"event": "done", "step": "complete", "progress": 100, "data": {"timepoint_id": "..."}}

data: {"event": "error", "error": "Error message", "progress": 0}
```

**Step Error Handling:**
If a step fails, an error event is emitted but the pipeline continues if possible:
```
data: {"event": "step_error", "step": "image_gen", "error": "Image generation failed", "progress": 95}
```

---

### GET /api/v1/timepoints/{id}

Get a timepoint by ID.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| include_image | boolean | false | Include base64 image data if available |

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "signing of the declaration",
  "slug": "signing-declaration-1776",
  "status": "completed",
  "year": 1776,
  "month": 7,
  "day": 4,
  "season": "summer",
  "time_of_day": "afternoon",
  "era": "American Revolution",
  "location": "Independence Hall, Philadelphia",
  "metadata": {...},
  "characters": {...},
  "scene": {...},
  "dialog": [...],
  "image_prompt": "...",
  "image_url": "...",
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:01:00Z",
  "parent_id": null,
  "error": null
}
```

**Errors:**
- 404: Timepoint not found

---

### GET /api/v1/timepoints/slug/{slug}

Get a timepoint by URL slug.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| slug | string | URL-safe slug |

**Response:** Same as GET /api/v1/timepoints/{id}

---

### GET /api/v1/timepoints

List timepoints with pagination.

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| page | int | 1 | Page number (min: 1) |
| page_size | int | 20 | Items per page (1-100) |

**Response (200 OK):**
```json
{
  "items": [...],
  "total": 42,
  "page": 1,
  "page_size": 20
}
```

---

### DELETE /api/v1/timepoints/{id}

Delete a timepoint and its associated generation logs.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

**Response (200 OK):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "deleted": true,
  "message": "Timepoint deleted successfully"
}
```

**Errors:**
- 404: Timepoint not found

---

## Temporal Navigation API

### POST /api/v1/temporal/{id}/next

Generate the next temporal moment from a timepoint.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Source timepoint UUID |

**Request Body:**
```json
{
  "units": 1,
  "unit": "day"
}
```

| Field | Type | Default | Range | Description |
|-------|------|---------|-------|-------------|
| units | int | 1 | 1-365 | Number of time units |
| unit | string | "day" | - | Time unit (second, minute, hour, day, week, month, year) |

**Response (200 OK):**
```json
{
  "source_id": "...",
  "target_id": "...",
  "source_year": 1776,
  "target_year": 1776,
  "direction": "next",
  "units": 1,
  "unit": "day",
  "message": "Generated moment 1 day(s) forward"
}
```

**Errors:**
- 400: Source timepoint not completed
- 404: Source timepoint not found
- 422: Invalid units value

---

### POST /api/v1/temporal/{id}/prior

Generate the prior temporal moment from a timepoint.

**Parameters and Request Body:** Same as /next

**Response:** Same structure with `direction: "prior"`

---

### GET /api/v1/temporal/{id}/sequence

Get the temporal sequence (linked prior and next timepoints).

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Center timepoint UUID |

**Query Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| direction | string | "both" | "prior", "next", or "both" |
| limit | int | 10 | Max timepoints per direction (1-50) |

**Response (200 OK):**
```json
{
  "center": {
    "id": "...",
    "year": 1776,
    "slug": "signing-declaration-1776"
  },
  "prior": [
    {"id": "...", "year": 1775, "slug": "..."},
    {"id": "...", "year": 1774, "slug": "..."}
  ],
  "next": [
    {"id": "...", "year": 1777, "slug": "..."}
  ]
}
```

---

## Models API

### GET /api/v1/models

List available LLM models.

**Query Parameters:**
| Name | Type | Description |
|------|------|-------------|
| provider | string | Filter by provider ("google" or "openrouter") |
| capability | string | Filter by capability ("text", "vision", "image_generation") |
| fetch_remote | boolean | Fetch dynamic models from OpenRouter API |

**Response (200 OK):**
```json
{
  "models": [
    {
      "id": "gemini-2.5-flash",
      "name": "Gemini 2.5 Flash",
      "provider": "google",
      "capabilities": ["text", "vision"],
      "context_length": 1000000,
      "pricing": null,
      "is_available": true
    },
    {
      "id": "anthropic/claude-3.5-sonnet",
      "name": "Claude 3.5 Sonnet",
      "provider": "openrouter",
      "capabilities": ["text", "vision"],
      "context_length": 200000,
      "pricing": {"prompt": 0.000003, "completion": 0.000015},
      "is_available": true
    }
  ],
  "total": 6,
  "cached": false
}
```

---

### GET /api/v1/models/providers

Get status of configured providers.

**Response (200 OK):**
```json
{
  "providers": [
    {
      "provider": "google",
      "available": true,
      "models_count": 3,
      "default_text_model": "gemini-2.5-flash",
      "default_image_model": "imagen-3.0-generate-002"
    },
    {
      "provider": "openrouter",
      "available": true,
      "models_count": 300,
      "default_text_model": "anthropic/claude-3.5-sonnet",
      "default_image_model": "google/gemini-3-pro-image-preview"
    }
  ]
}
```

---

### GET /api/v1/models/{model_id}

Get details for a specific model.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| model_id | string | Model identifier (supports path-like IDs) |

**Response (200 OK):** Single ModelInfo object

**Errors:**
- 404: Model not found

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request (invalid state) |
| 404 | Resource not found |
| 422 | Validation error |
| 500 | Internal server error |

---

## Rate Limiting

Default rate limit: 60 requests per minute per IP.

When exceeded, returns 429 Too Many Requests.

---

## Authentication

Currently, the API does not require authentication. API key authentication may be added in future versions.

---

## Character Interactions API

Interact with characters from generated timepoints through chat, dialog extension, and surveys.

---

### POST /api/v1/interactions/{id}/chat

Chat with a specific character from a timepoint.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

**Request Body:**
```json
{
  "character": "Benjamin Franklin",
  "message": "What do you think of this document?",
  "session_id": null,
  "save_session": false,
  "model": "gemini-2.5-flash",
  "response_format": "auto"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| character | string | Yes | - | Character name (case-insensitive) |
| message | string | Yes | - | User's message to character |
| session_id | string | No | null | Session ID to continue conversation |
| save_session | boolean | No | false | Whether to save session to memory |
| model | string | No | null | LLM model override (e.g., "gemini-2.5-flash", "anthropic/claude-3.5-sonnet") |
| response_format | string | No | "auto" | Response format: "auto", "structured" (JSON with emotional_tone), or "text" (plain) |

**Response (200 OK):**
```json
{
  "character_name": "Benjamin Franklin",
  "response": "My dear friend, this document represents the culmination of our highest aspirations...",
  "session_id": "abc123",
  "emotional_tone": "thoughtful",
  "latency_ms": 1250
}
```

**Errors:**
- 404: Timepoint or character not found
- 500: Chat generation failed

---

### POST /api/v1/interactions/{id}/chat/stream

Stream chat response with Server-Sent Events.

**Request Body:** Same as /chat

**Response:** Server-Sent Events (text/event-stream)

**Event Types:**
```
data: {"event": "token", "data": "My ", "character_name": "Benjamin Franklin"}
data: {"event": "token", "data": "dear ", "character_name": "Benjamin Franklin"}
...
data: {"event": "done", "data": "Full response text", "character_name": "Benjamin Franklin"}
data: {"event": "error", "data": "Error message"}
```

---

### POST /api/v1/interactions/{id}/dialog

Generate additional dialog between characters.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

**Request Body:**
```json
{
  "characters": "all",
  "num_lines": 5,
  "prompt": "They begin discussing the risks of signing",
  "sequential": true,
  "model": "gemini-2.5-flash",
  "response_format": "auto"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| characters | string or array | No | "all" | "all" or list of character names |
| num_lines | int | No | 5 | Number of lines (1-10) |
| prompt | string | No | null | Direction for the dialog |
| sequential | boolean | No | true | Use sequential roleplay generation |
| model | string | No | null | LLM model override (e.g., "gemini-2.5-flash") |
| response_format | string | No | "auto" | Response format (dialog always uses structured JSON) |

**Response (200 OK):**
```json
{
  "dialog": [
    {"speaker": "John Adams", "line": "We must consider the consequences..."},
    {"speaker": "Benjamin Franklin", "line": "Indeed, we are all putting our necks on the line."}
  ],
  "context": "The founders discuss the gravity of their decision",
  "characters_involved": ["John Adams", "Benjamin Franklin"],
  "latency_ms": 2500
}
```

---

### POST /api/v1/interactions/{id}/dialog/stream

Stream dialog generation line by line.

**Request Body:** Same as /dialog

**Response:** Server-Sent Events (text/event-stream)

**Event Types:**
```
data: {"event": "line", "data": {"speaker": "John Adams", "line": "..."}}
data: {"event": "line", "data": {"speaker": "Benjamin Franklin", "line": "..."}}
data: {"event": "done", "data": {"dialog": [...], "characters_involved": [...]}}
data: {"event": "error", "data": "Error message"}
```

---

### POST /api/v1/interactions/{id}/survey

Survey multiple characters with the same questions.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

**Request Body:**
```json
{
  "characters": "all",
  "questions": ["What do you fear most about this moment?"],
  "mode": "parallel",
  "chain_prompts": false,
  "include_summary": true,
  "model": "gemini-2.5-flash",
  "response_format": "structured"
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| characters | string or array | No | "all" | "all" or list of character names |
| questions | array | Yes | - | Questions to ask each character |
| mode | string | No | "parallel" | "parallel" (faster) or "sequential" (context-aware) |
| chain_prompts | boolean | No | false | In sequential mode, share prior answers |
| include_summary | boolean | No | true | Generate summary of responses |
| model | string | No | null | LLM model override (e.g., "gemini-2.5-flash") |
| response_format | string | No | "auto" | "auto", "structured" (JSON with sentiment/key_points/emotional_tone), or "text" |

**Response (200 OK):**
```json
{
  "timepoint_id": "abc123",
  "questions": ["What do you fear most about this moment?"],
  "responses": [
    {
      "character_name": "John Adams",
      "question": "What do you fear most?",
      "response": "That we shall all hang for this act of treason...",
      "sentiment": "negative",
      "key_points": ["fear of execution", "uncertainty"],
      "emotional_tone": "anxious"
    },
    {
      "character_name": "Benjamin Franklin",
      "question": "What do you fear most?",
      "response": "I fear not death, but rather that we might fail...",
      "sentiment": "mixed",
      "key_points": ["acceptance of risk", "concern for success"],
      "emotional_tone": "resolute"
    }
  ],
  "summary": "The founders express a mixture of fear and determination...",
  "mode": "parallel",
  "total_characters": 2,
  "latency_ms": 3500
}
```

**Survey Modes:**
- **parallel**: Query all characters simultaneously (faster)
- **sequential**: Query characters one by one with context sharing

**Sentiment Values:**
- `positive` - Optimistic, hopeful response
- `negative` - Fearful, worried response
- `mixed` - Complex emotional response
- `neutral` - Factual, unemotional response

---

### POST /api/v1/interactions/{id}/survey/stream

Stream survey results as each character responds.

**Request Body:** Same as /survey

**Response:** Server-Sent Events (text/event-stream)

**Event Types:**
```
data: {"event": "start", "total_characters": 8}
data: {"event": "response", "data": {"character_name": "John Adams", "response": "...", "sentiment": "negative"}}
data: {"event": "response", "data": {"character_name": "Benjamin Franklin", ...}}
data: {"event": "summary", "data": "The founders express..."}
data: {"event": "done", "total_responses": 8, "latency_ms": 5000}
data: {"event": "error", "data": "Error message"}
```

---

### GET /api/v1/interactions/sessions/{timepoint_id}

List chat sessions for a timepoint.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| timepoint_id | string | Timepoint UUID |

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": "session-123",
      "character_name": "Benjamin Franklin",
      "message_count": 5,
      "last_message_preview": "Indeed, liberty requires...",
      "created_at": "2025-01-01T12:00:00Z",
      "updated_at": "2025-01-01T12:05:00Z"
    }
  ],
  "total": 1
}
```

---

### GET /api/v1/interactions/session/{session_id}

Get a chat session with full message history.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| session_id | string | Session UUID |

**Response (200 OK):**
```json
{
  "id": "session-123",
  "timepoint_id": "tp-456",
  "character_name": "Benjamin Franklin",
  "messages": [
    {"role": "user", "content": "What do you think?", "timestamp": "..."},
    {"role": "character", "content": "My dear friend...", "character_name": "Benjamin Franklin", "timestamp": "..."}
  ],
  "created_at": "2025-01-01T12:00:00Z",
  "updated_at": "2025-01-01T12:05:00Z"
}
```

**Errors:**
- 404: Session not found

---

### DELETE /api/v1/interactions/session/{session_id}

Delete a chat session.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| session_id | string | Session UUID |

**Response (200 OK):**
```json
{
  "deleted": true,
  "session_id": "session-123"
}
```

**Errors:**
- 404: Session not found

---

## OpenAPI Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
