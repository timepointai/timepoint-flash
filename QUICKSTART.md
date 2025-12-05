# TIMEPOINT Flash Quick Start Guide

Get up and running with TIMEPOINT Flash in 5 minutes.

---

## 1. Prerequisites

- **Python 3.10+** (required for SQLAlchemy compatibility)
- **API Key**: Google API key or OpenRouter API key

### Check Python Version

```bash
python3 --version
# Should be 3.10 or higher

# If you have multiple versions, use python3.10 explicitly
python3.10 --version
```

---

## 2. Installation

### Clone and Install

```bash
# Clone the repository
git clone https://github.com/realityinspector/timepoint-flash.git
cd timepoint-flash

# Create virtual environment (optional but recommended)
python3.10 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install package and dependencies
pip install -e .
```

### Configure API Keys

Create a `.env` file in the project root:

```bash
# Option 1: Google AI (recommended for best results)
GOOGLE_API_KEY=your-google-api-key

# Option 2: OpenRouter (300+ model options)
OPENROUTER_API_KEY=your-openrouter-api-key

# You can use both for fallback support
```

Or export directly:

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

---

## 3. Start the Server

```bash
# Start FastAPI with auto-reload
uvicorn app.main:app --reload

# Or with explicit port
uvicorn app.main:app --reload --port 8000
```

### Verify Server is Running

```bash
# Check root health
curl http://localhost:8000/health
# Returns: {"status": "healthy", "version": "2.0.0"}

# Check API health
curl http://localhost:8000/api/v1/health
# Returns: {"status": "healthy", "database": "connected"}
```

---

## 4. Generate Your First Timepoint

### Option A: Streaming (Recommended)

Watch the generation progress in real-time:

```bash
curl -N http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence"}'
```

You'll see events like:
```
data: {"event": "start", "step": "initialization", "progress": 0}
data: {"event": "step_complete", "step": "judge", "progress": 10}
data: {"event": "step_complete", "step": "timeline", "progress": 20}
...
data: {"event": "done", "step": "complete", "progress": 100, "data": {"timepoint_id": "..."}}
```

### Option B: Async Generation

Start generation and poll for completion:

```bash
# Start generation
curl -X POST http://localhost:8000/api/v1/timepoints/generate \
  -H "Content-Type: application/json" \
  -d '{"query": "rome 50 BCE"}'
# Returns: {"id": "...", "status": "processing", "message": "..."}

# Check status
curl http://localhost:8000/api/v1/timepoints/{id}
```

---

## 5. Explore the Results

### Get Timepoint by ID

```bash
curl http://localhost:8000/api/v1/timepoints/{timepoint-id}
```

Response includes:
- Temporal data (year, month, day, season, time_of_day)
- Location
- Characters (up to 8)
- Scene description
- Dialog lines (up to 7)
- Image prompt
- Generated image URL (if requested)

### List All Timepoints

```bash
curl "http://localhost:8000/api/v1/timepoints?page=1&page_size=10"
```

---

## 6. Temporal Navigation

Navigate through time from an existing timepoint:

### Generate Next Moment

```bash
curl -X POST http://localhost:8000/api/v1/temporal/{timepoint-id}/next \
  -H "Content-Type: application/json" \
  -d '{"units": 1, "unit": "day"}'
```

### Generate Prior Moment

```bash
curl -X POST http://localhost:8000/api/v1/temporal/{timepoint-id}/prior \
  -H "Content-Type: application/json" \
  -d '{"units": 10, "unit": "year"}'
```

### Get Temporal Sequence

```bash
curl "http://localhost:8000/api/v1/temporal/{timepoint-id}/sequence?direction=both&limit=10"
```

---

## 7. Model Discovery

### List Available Models

```bash
curl http://localhost:8000/api/v1/models
```

### Filter by Provider

```bash
curl "http://localhost:8000/api/v1/models?provider=google"
```

### Filter by Capability

```bash
curl "http://localhost:8000/api/v1/models?capability=text"
curl "http://localhost:8000/api/v1/models?capability=image_generation"
```

### Check Provider Status

```bash
curl http://localhost:8000/api/v1/models/providers
```

---

## 8. Generate with Image

Request image generation along with the timepoint:

```bash
curl -N http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "ancient egypt pyramids construction", "generate_image": true}'
```

---

## 9. Run Tests

Verify everything is working:

```bash
# Run fast unit tests (no API calls needed)
python3.10 -m pytest -m fast -v

# Run integration tests (requires database)
python3.10 -m pytest -m integration -v
```

---

## Common Issues

### "No API keys configured" Error

Ensure at least one API key is set:
```bash
echo $GOOGLE_API_KEY
# or
echo $OPENROUTER_API_KEY
```

### SQLAlchemy/Python Version Issues

Use Python 3.10 explicitly:
```bash
python3.10 -m pytest -m fast
```

### Database Not Found

The database is auto-created on first request. If issues persist:
```bash
# Delete and recreate
rm -f timepoint.db test_timepoint.db
```

---

## 10. Character Interactions

After generating a timepoint, you can interact with its characters:

### Chat with a Character

```bash
curl -X POST http://localhost:8000/api/v1/interactions/{timepoint-id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character": "Benjamin Franklin", "message": "What do you think of this document?"}'
```

Response:
```json
{
  "character_name": "Benjamin Franklin",
  "response": "My dear friend, I believe this document shall echo through the ages...",
  "emotional_tone": "thoughtful",
  "latency_ms": 1250
}
```

### Extend the Dialog

Generate more dialog between characters:

```bash
curl -X POST http://localhost:8000/api/v1/interactions/{timepoint-id}/dialog \
  -H "Content-Type: application/json" \
  -d '{"characters": "all", "num_lines": 5, "prompt": "They discuss the risks of signing"}'
```

### Survey Characters

Ask the same question to all characters and get structured responses:

```bash
curl -X POST http://localhost:8000/api/v1/interactions/{timepoint-id}/survey \
  -H "Content-Type: application/json" \
  -d '{"characters": "all", "questions": ["What do you fear most about this moment?"]}'
```

Response includes sentiment analysis:
```json
{
  "responses": [
    {
      "character_name": "John Adams",
      "question": "What do you fear most?",
      "response": "That we shall all hang for this...",
      "sentiment": "negative",
      "emotional_tone": "anxious"
    }
  ]
}
```

---

## Next Steps

- Read the [API Reference](docs/API.md) for complete endpoint documentation
- Learn about [Temporal Navigation](docs/TEMPORAL.md) for time-travel features
- Explore [Character Interactions](docs/API.md#character-interactions-api) for chat, dialog, and survey
- Run the full test suite with `pytest -v`

---

## Example Queries

Try these to explore different historical moments:

```bash
# Ancient History
"rome 50 BCE"
"ancient egypt during pyramid construction"
"athens at the height of democracy"

# Medieval
"signing of the magna carta"
"black death arrives in london"

# Modern History
"signing of the declaration of independence"
"moon landing 1969"
"fall of the berlin wall"

# Specific Events
"assassination of julius caesar"
"leonardo painting the mona lisa"
"first flight at kitty hawk"
```
