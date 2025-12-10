# TIMEPOINT Flash

AI-powered historical scene generator. Give it a moment in history, get back a fully-realized scene with characters, dialog, relationships, and an AI-generated image.

```
"signing of the declaration of independence"
                    ↓
    Scene + 8 Characters + Dialog + Relationships + Image
```

## What It Generates

| Output | Example |
|--------|---------|
| **When** | July 4, 1776, afternoon, summer |
| **Where** | Independence Hall, Philadelphia |
| **Who** | Up to 8 characters with bios, appearances, personalities |
| **What** | Scene description, atmosphere, tension level |
| **Dialog** | 7 period-appropriate lines |
| **Relationships** | Alliances, rivalries, tensions between characters |
| **Image** | Photorealistic AI-generated scene |

After generation, you can **chat with characters**, extend the dialog, or survey all characters with questions.

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and add your API key
```

You need at least one API key:
- `GOOGLE_API_KEY` - For Google Gemini models (recommended)
- `OPENROUTER_API_KEY` - For OpenRouter multi-model access

### 3. Run

**Option A: Interactive Demo (recommended for first-time users)**

```bash
# Terminal 1: Start the server
./run.sh -r

# Terminal 2: Run the interactive demo
./demo.sh
```

The demo provides a menu-driven interface for generating timepoints, browsing results, chatting with characters, and more.

**Option B: API Server Only**

```bash
# Start server with auto-reload (development)
./run.sh -r

# Or use uvicorn directly
uvicorn app.main:app --reload
```

Then use the API at `http://localhost:8000`. Interactive docs at `/docs`.

**Option C: Single API Call**

```bash
# Start server in background
./run.sh &

# Generate a timepoint
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence"}'
```

---

## Server Script Options

```bash
./run.sh [options]

Options:
  -r, --reload      Enable auto-reload (development mode)
  -p, --port PORT   Set port (default: 8000, auto-finds available)
  -d, --debug       Enable debug logging
  -P, --prod        Production mode (0.0.0.0, 4 workers)
  -k, --kill        Kill existing process on port before starting
  --help            Show all options
```

---

## API Overview

### Timepoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/timepoints/generate` | Generate (async, returns ID) |
| POST | `/api/v1/timepoints/generate/stream` | Generate with SSE progress |
| GET | `/api/v1/timepoints/{id}` | Get by ID |
| GET | `/api/v1/timepoints` | List with pagination |
| DELETE | `/api/v1/timepoints/{id}` | Delete |

### Character Interactions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/interactions/{id}/chat` | Chat with a character |
| POST | `/api/v1/interactions/{id}/dialog` | Generate more dialog |
| POST | `/api/v1/interactions/{id}/survey` | Survey all characters |

All interaction endpoints have `/stream` variants for SSE.

### Temporal Navigation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/temporal/{id}/next` | Generate next moment |
| POST | `/api/v1/temporal/{id}/prior` | Generate prior moment |
| GET | `/api/v1/temporal/{id}/sequence` | Get linked sequence |

### Models

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/models` | List available models |
| GET | `/api/v1/models/providers` | Provider status |

Full API reference: [docs/API.md](docs/API.md)

---

## Architecture

### Generation Pipeline

15 specialized AI agents process each query:

```
Query → Judge → Timeline → Scene → Characters → Graph → Moment → Dialog → Camera → ImagePrompt → Image
```

1. **JudgeAgent** - Validates query, classifies type
2. **TimelineAgent** - Extracts temporal coordinates
3. **SceneAgent** - Creates environment and atmosphere
4. **CharacterIdentificationAgent** - Identifies key figures
5. **GraphAgent** - Maps character relationships
6. **CharacterBioAgent** - Generates detailed bios (parallel)
7. **MomentAgent** - Defines plot, tension, stakes
8. **DialogAgent** - Writes period-appropriate dialog
9. **CameraAgent** - Composition and framing
10. **ImagePromptAgent** - Assembles image generation prompt
11. **ImageGenAgent** - Generates photorealistic image

Plus 3 interaction agents: **CharacterChatAgent**, **DialogExtensionAgent**, **SurveyAgent**

### Providers

- **Google AI** - Gemini 2.5 Flash (text + image)
- **OpenRouter** - 300+ models including Claude, GPT-4o

---

## Configuration

### Environment Variables

```bash
# Required (at least one)
GOOGLE_API_KEY=your-key
OPENROUTER_API_KEY=your-key

# Database
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db

# Provider selection
PRIMARY_PROVIDER=google
FALLBACK_PROVIDER=openrouter

# Model selection
JUDGE_MODEL=gemini-2.5-flash
CREATIVE_MODEL=gemini-2.5-flash
IMAGE_MODEL=gemini-2.5-flash-image

# Pipeline parallelism (1-5)
PIPELINE_MAX_PARALLELISM=3
```

See `.env.example` for all options.

### Quality Presets (Demo)

| Preset | Model | Speed | Quality |
|--------|-------|-------|---------|
| **HD** | Gemini 2.5 Flash + extended thinking | ~4-6 min | Highest |
| **Balanced** | Gemini 2.5 Flash | ~2-4 min | Good |
| **Hyper** | Gemini 2.0 Flash via OpenRouter | ~1-2 min | Adequate |

---

## Development

### Run Tests

```bash
# Fast unit tests (~6 seconds)
python3.10 -m pytest -m fast -v

# Full test suite (514 tests)
python3.10 -m pytest -v

# With coverage
python3.10 -m pytest --cov=app -v
```

### Project Structure

```
timepoint-flash/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings and model configs
│   ├── models.py            # SQLAlchemy ORM models
│   ├── database.py          # Database connection
│   ├── agents/              # 15 AI agent implementations
│   ├── core/                # Pipeline, router, providers
│   ├── schemas/             # Pydantic response models
│   ├── prompts/             # Prompt templates
│   └── api/v1/              # REST endpoints
├── tests/                   # Unit and integration tests
├── docs/                    # Additional documentation
├── run.sh                   # Server start script
└── demo.sh                  # Interactive demo CLI
```

### Type Checking & Linting

```bash
mypy app/
ruff check app/
```

---

## Documentation

- [docs/AGENTS.md](docs/AGENTS.md) - Multi-agent architecture
- [docs/API.md](docs/API.md) - Complete API reference
- [docs/TEMPORAL.md](docs/TEMPORAL.md) - Temporal navigation

---

## License

Apache License 2.0 - see LICENSE file.

---

**Tech Stack**: FastAPI | SQLAlchemy | Google Gemini | Pydantic | Python 3.10+

**Version**: 2.2.1
