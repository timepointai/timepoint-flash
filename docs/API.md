# TIMEPOINT Flash - Public API Documentation

## TL;DR for Lazy Devs

**No authentication required. Just send requests and get results.**

```bash
# Generate a timepoint
curl -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{"input_query": "Medieval marketplace, London 1250", "requester_email": "dev@example.com"}'

# Get all results
curl http://localhost:8000/api/feed | jq '.'
```

That's it. 🎉

---

## Quick Start

### Start the Server

```bash
./tp serve
# Server runs on http://localhost:8000
```

### Generate Your First Timepoint

```bash
curl -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{
    "input_query": "Ancient Rome forum, summer 50 BCE",
    "requester_email": "you@example.com"
  }'
```

**Response:**
```json
{
  "session_id": "abc123-def456",
  "slug": "ancient-rome-forum-50-bce-summer",
  "status": "started",
  "message": "Timepoint generation started"
}
```

### Watch Progress (Server-Sent Events)

```bash
curl -N http://localhost:8000/api/timepoint/status/abc123-def456
```

**Stream Output:**
```
event: progress
data: {"agent": "judge", "message": "Validating query", "progress": 10}

event: progress
data: {"agent": "timeline", "message": "Building timeline", "progress": 20}

...

event: complete
data: {"slug": "ancient-rome-forum-50-bce-summer", "status": "complete"}
```

### Get Results

```bash
# List all timepoints
curl http://localhost:8000/api/feed?limit=10 | jq '.'

# Get specific timepoint
curl http://localhost:8000/api/timepoint/details/ancient-rome-forum-50-bce-summer | jq '.'
```

---

## API Endpoints

### Health Check

```
GET /health
```

Check if the server is running.

**Example:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "timepoint-flash"
}
```

---

### Create Timepoint

```
POST /api/timepoint/create
```

Generate a new historical scene.

**Request Body:**
```json
{
  "input_query": "string (required) - Historical scene description",
  "requester_email": "string (optional) - Email for rate limiting"
}
```

**Response:**
```json
{
  "session_id": "string - Track generation progress",
  "slug": "string - Unique identifier",
  "status": "started",
  "message": "Timepoint generation started"
}
```

**Example:**
```bash
curl -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{
    "input_query": "Victorian London street, foggy evening 1888",
    "requester_email": "dev@example.com"
  }'
```

---

### Get Generation Status (SSE Stream)

```
GET /api/timepoint/status/{session_id}
```

Real-time progress updates via Server-Sent Events.

**Example:**
```bash
curl -N http://localhost:8000/api/timepoint/status/abc123-def456
```

**Events:**
- `progress` - Agent updates with progress percentage
- `complete` - Generation finished successfully
- `error` - Something went wrong

---

### List All Timepoints (Feed)

```
GET /api/feed?limit={limit}&offset={offset}
```

Get paginated list of all generated timepoints.

**Query Parameters:**
- `limit` (optional, default: 20) - Number of results per page
- `offset` (optional, default: 0) - Pagination offset

**Response:**
```json
{
  "timepoints": [
    {
      "slug": "medieval-marketplace-london-1250-winter",
      "input_query": "Medieval marketplace in London, winter 1250",
      "year": 1250,
      "season": "winter",
      "image_url": "https://...",
      "character_data_json": [...],
      "dialog_json": [...],
      "processing_time_ms": 45000,
      "created_at": "2024-11-26T10:30:00Z"
    }
  ],
  "total": 42,
  "has_more": true
}
```

**Example:**
```bash
curl "http://localhost:8000/api/feed?limit=5&offset=0" | jq '.'
```

---

### Get Timepoint Details

```
GET /api/timepoint/details/{slug}
```

Get complete data for a specific timepoint.

**Example:**
```bash
curl http://localhost:8000/api/timepoint/details/medieval-marketplace-london-1250-winter | jq '.'
```

**Response:** Full timepoint object with all fields.

---

### Check Timepoint Status

```
GET /api/timepoint/check/{slug}
```

Quick status check (without SSE stream).

**Response:**
```json
{
  "slug": "string",
  "status": "processing|complete|failed",
  "progress": 75,
  "error": "string (if failed)"
}
```

---

## Rate Limiting

- **Email-based**: 1 generation per hour per email
- **IP-based**: 10 generations per hour for anonymous requests
- **Trusted hosts**: Unlimited (replit.dev, timepointai.com)

**Rate Limit Response:**
```json
{
  "detail": "Rate limit exceeded. You can create 1 timepoint per hour. Please wait 45 minutes."
}
```

---

## Response Schema

### Timepoint Object

```json
{
  "id": "uuid",
  "slug": "unique-identifier-with-context",
  "input_query": "Original query from user",
  "cleaned_query": "Processed query",
  "year": 1250,
  "season": "winter",
  "location": "London",
  "image_url": "https://storage.../image.jpg",
  "scene_graph_svg": "<svg>...</svg>",
  "character_data_json": [
    {
      "name": "John the Merchant",
      "age": 45,
      "role": "Shopkeeper",
      "clothing": "Brown wool tunic, leather apron",
      "description": "Weathered face, warm smile"
    }
  ],
  "dialog_json": [
    {
      "character": "John the Merchant",
      "text": "Fresh bread, still warm from the oven!"
    }
  ],
  "timeline_data_json": {...},
  "camera_settings": {...},
  "metadata_json": {...},
  "processing_time_ms": 45000,
  "created_at": "2024-11-26T10:30:00Z"
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Human-readable error message"
}
```

**Common HTTP Status Codes:**
- `200` - Success
- `400` - Bad request (invalid input)
- `404` - Not found
- `429` - Rate limit exceeded
- `500` - Server error

---

## Code Examples

### Python

```python
import requests
import json

# Generate timepoint
response = requests.post(
    "http://localhost:8000/api/timepoint/create",
    json={
        "input_query": "Medieval marketplace, London 1250",
        "requester_email": "dev@example.com"
    }
)
data = response.json()
session_id = data["session_id"]
slug = data["slug"]

print(f"Generation started: {slug}")

# Wait a bit for generation to complete (usually 40-60 seconds)
import time
time.sleep(60)

# Get results
feed = requests.get("http://localhost:8000/api/feed?limit=1").json()
timepoint = feed["timepoints"][0]

print(f"Image URL: {timepoint['image_url']}")
print(f"Characters: {len(timepoint['character_data_json'])}")
```

### JavaScript

```javascript
// Generate timepoint
const response = await fetch('http://localhost:8000/api/timepoint/create', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    input_query: 'Medieval marketplace, London 1250',
    requester_email: 'dev@example.com'
  })
});

const { session_id, slug } = await response.json();
console.log('Generation started:', slug);

// Watch progress with EventSource (SSE)
const eventSource = new EventSource(
  `http://localhost:8000/api/timepoint/status/${session_id}`
);

eventSource.addEventListener('progress', (e) => {
  const data = JSON.parse(e.data);
  console.log(`[${data.agent}] ${data.message} - ${data.progress}%`);
});

eventSource.addEventListener('complete', async (e) => {
  const data = JSON.parse(e.data);
  console.log('Complete!', data.slug);
  eventSource.close();

  // Get full details
  const details = await fetch(
    `http://localhost:8000/api/timepoint/details/${data.slug}`
  ).then(r => r.json());

  console.log('Image URL:', details.image_url);
  console.log('Characters:', details.character_data_json);
});
```

### curl + jq

```bash
#!/bin/bash

# Generate timepoint
SESSION_ID=$(curl -s -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{"input_query": "Medieval London 1250", "requester_email": "dev@example.com"}' \
  | jq -r '.session_id')

echo "Generating... (session: $SESSION_ID)"

# Watch progress
curl -N http://localhost:8000/api/timepoint/status/$SESSION_ID | while read line; do
  echo "$line"
done

# Get latest result
echo "Getting results..."
curl -s http://localhost:8000/api/feed?limit=1 | jq '.timepoints[0] | {
  slug: .slug,
  year: .year,
  season: .season,
  characters: .character_data_json | length,
  image_url: .image_url
}'
```

---

## Interactive API Docs

Visit `http://localhost:8000/api/docs` for interactive Swagger UI where you can test all endpoints in your browser.

---

## Need Help?

- **Documentation**: See [README.md](../README.md) for setup
- **Examples**: See [examples/](../examples/) for working code
- **Models**: See [MODELS.md](MODELS.md) for AI model information
- **Issues**: https://github.com/realityinspector/timepoint-flash/issues

---

**Built with ⚡ FastAPI | 🧠 LangGraph | 🍌 Gemini 2.5 "Nano Banana"**
