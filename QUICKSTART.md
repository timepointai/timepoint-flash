# TIMEPOINT Flash Quick Start Guide

Get up and running in 2 minutes.

---

## Fastest Path: Interactive Demo

```bash
# 1. Clone & install
git clone https://github.com/realityinspector/timepoint-flash.git
cd timepoint-flash
pip install -e .

# 2. Set your API key
export GOOGLE_API_KEY="your-key"

# 3. Run the demo
./demo.sh
```

That's it! The demo starts the server and gives you a menu to:
- Generate timepoints with different presets (HD, Balanced, Hyper)
- Browse and view generated timepoints
- Chat with characters from any scene
- Extend dialog or survey all characters

---

## Manual Setup (for API access)

### Prerequisites

- Python 3.10+ (`python3.10 --version`)
- API Key: [Google AI](https://aistudio.google.com/) or [OpenRouter](https://openrouter.ai/)

### Installation

```bash
git clone https://github.com/realityinspector/timepoint-flash.git
cd timepoint-flash

# Optional: use virtual environment
python3.10 -m venv .venv && source .venv/bin/activate

pip install -e .
```

### Configure API Key

```bash
# Option 1: Export directly
export GOOGLE_API_KEY="your-key"

# Option 2: Create .env file
echo 'GOOGLE_API_KEY=your-key' > .env
```

### Start Server

```bash
uvicorn app.main:app --reload
# Server at http://localhost:8000
```

### Generate Your First Timepoint

```bash
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence"}'
```

Watch the 15 agents work in real-time:
```
data: {"event": "step_complete", "step": "judge", "progress": 10}
data: {"event": "step_complete", "step": "timeline", "progress": 20}
data: {"event": "step_complete", "step": "scene", "progress": 30}
...
data: {"event": "done", "progress": 100, "data": {"timepoint_id": "abc123"}}
```

---

## Explore the Results

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

## Temporal Navigation

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

## Model Discovery

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

## Generate with Image

Request image generation along with the timepoint:

```bash
curl -N http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "ancient egypt pyramids construction", "generate_image": true}'
```

---

## Run Tests

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

## Character Interactions

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
