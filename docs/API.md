# TIMEPOINT Flash API Reference

Complete API documentation for TIMEPOINT Flash v2.0.

Base URL: `http://localhost:8000`

---

## Health Endpoints

### GET /health

Root health check.

**Response:**
```json
{
  "status": "healthy",
  "version": "2.0.0"
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

Generate a timepoint with real-time SSE progress events.

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
| generate_image | boolean | No | false | Whether to generate image |

**Response:** Server-Sent Events (text/event-stream)

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

data: {"event": "done", "step": "complete", "progress": 100, "data": {"timepoint_id": "..."}}

data: {"event": "error", "error": "Error message", "progress": 0}
```

---

### GET /api/v1/timepoints/{id}

Get a timepoint by ID.

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| id | string | Timepoint UUID |

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

## OpenAPI Documentation

Interactive API docs available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
