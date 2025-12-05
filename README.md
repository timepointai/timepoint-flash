# TIMEPOINT Flash v2.0

AI-powered photorealistic time travel system with multi-agent workflows, temporal navigation, character interactions, and batteries-included developer experience.

---

## Overview

TIMEPOINT Flash generates immersive historical moments using a pipeline of 12 specialized AI agents. Given a natural language query like "signing of the declaration of independence", it produces:

- Validated temporal coordinates (year, season, time of day)
- Detailed scene environment and atmosphere
- Up to 8 historically-accurate characters
- Period-appropriate dialog (7 lines)
- Camera composition and framing
- Character relationship graph
- Photorealistic image prompt
- Optional generated image

**NEW in v2.1**: Chat with characters, extend dialog, and survey characters for their perspectives.

## Quick Start

### Prerequisites

- Python 3.10+
- Google API key (for Gemini models) and/or OpenRouter API key

### Installation

```bash
# Clone repository
git clone https://github.com/realityinspector/timepoint-flash.git
cd timepoint-flash

# Install dependencies
pip install -e .

# Set API keys
export GOOGLE_API_KEY="your-google-api-key"
# or
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

### Run the Server

```bash
# Start FastAPI server
uvicorn app.main:app --reload

# Check health
curl http://localhost:8000/health
```

### Generate a Timepoint

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/timepoints/generate \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence"}'

# Streaming (SSE)
curl -N http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "rome 50 BCE"}'
```

---

## API Reference

### Timepoints API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/timepoints/generate` | Generate timepoint (async) |
| POST | `/api/v1/timepoints/generate/stream` | Generate with SSE streaming |
| GET | `/api/v1/timepoints/{id}` | Get timepoint by ID |
| GET | `/api/v1/timepoints/slug/{slug}` | Get timepoint by slug |
| GET | `/api/v1/timepoints` | List timepoints (pagination) |
| DELETE | `/api/v1/timepoints/{id}` | Delete timepoint |

### Temporal Navigation API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/temporal/{id}/next` | Generate next moment |
| POST | `/api/v1/temporal/{id}/prior` | Generate prior moment |
| GET | `/api/v1/temporal/{id}/sequence` | Get temporal sequence |

### Models API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/models` | List available models |
| GET | `/api/v1/models/providers` | Provider status |
| GET | `/api/v1/models/{model_id}` | Model details |

### Character Interactions API

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/interactions/{id}/chat` | Chat with a character |
| POST | `/api/v1/interactions/{id}/chat/stream` | Stream chat response |
| POST | `/api/v1/interactions/{id}/dialog` | Generate more dialog |
| POST | `/api/v1/interactions/{id}/dialog/stream` | Stream dialog lines |
| POST | `/api/v1/interactions/{id}/survey` | Survey all characters |
| POST | `/api/v1/interactions/{id}/survey/stream` | Stream survey results |
| GET | `/api/v1/interactions/sessions/{id}` | List chat sessions |

---

## Architecture

### Agent Pipeline

```
Query -> JudgeAgent -> TimelineAgent -> SceneAgent -> CharactersAgent
                                                           |
ImageGenAgent <- ImagePromptAgent <- GraphAgent <- CameraAgent <- DialogAgent <- MomentAgent
```

### 12 Specialized Agents

**Generation Pipeline:**
1. **JudgeAgent** - Query validation and classification
2. **TimelineAgent** - Temporal coordinate extraction
3. **SceneAgent** - Environment and atmosphere
4. **CharactersAgent** - Up to 8 characters with roles
5. **MomentAgent** - Plot, tension, and stakes
6. **DialogAgent** - Period-appropriate dialog (7 lines)
7. **CameraAgent** - Composition and framing
8. **GraphAgent** - Character relationships
9. **ImagePromptAgent** - Assemble 11K character prompt
10. **ImageGenAgent** - Generate photorealistic image

**Character Interactions:**
11. **CharacterChatAgent** - Have conversations with characters
12. **DialogExtensionAgent** - Generate additional dialog lines
13. **SurveyAgent** - Survey multiple characters with questions

### Provider Support

- **Google AI** - Gemini 2.5 Flash, Gemini 3 Pro, Imagen 3
- **OpenRouter** - 300+ models including Claude, GPT-4o

---

## Configuration

### Environment Variables

```bash
# Required (at least one)
GOOGLE_API_KEY=your-key
OPENROUTER_API_KEY=your-key

# Optional
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db  # or postgresql://
PRIMARY_PROVIDER=google  # or openrouter
JUDGE_MODEL=gemini-2.5-flash
CREATIVE_MODEL=gemini-3-pro-preview
IMAGE_MODEL=google/gemini-3-pro-image-preview
LOGFIRE_TOKEN=your-token  # for observability
```

---

## Deployment

### Docker

```bash
# Production (with PostgreSQL)
docker compose up -d

# Development (with hot reload)
docker compose -f docker-compose.dev.yml up
```

### Cloud Platforms

- **Railway**: Auto-deploys with `railway.json`
- **Render**: Uses `render.yaml` Blueprint

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for complete deployment guide.

---

## Development

### Run Tests

```bash
# Fast unit tests (no API calls)
python3.10 -m pytest -m fast -v

# Integration tests
python3.10 -m pytest -m integration -v

# Full test suite
python3.10 -m pytest -v
```

### Test Coverage

- 265+ unit tests
- Covers all agents, schemas, API endpoints
- Fast tests complete in ~6 seconds

### Project Structure

```
timepoint-flash/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Pydantic settings
│   ├── models.py            # SQLAlchemy models
│   ├── database.py          # Database connection
│   ├── agents/              # 10 agent implementations
│   ├── core/                # Provider, router, temporal
│   ├── schemas/             # Pydantic response models
│   ├── prompts/             # Prompt templates
│   └── api/v1/              # API routes
├── tests/
│   ├── unit/                # Fast unit tests
│   └── integration/         # API integration tests
├── docs/                    # Additional documentation
└── archive/                 # v1.0 legacy code
```

---

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Step-by-step getting started guide
- [docs/API.md](docs/API.md) - Complete API reference
- [docs/TEMPORAL.md](docs/TEMPORAL.md) - Temporal navigation guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guide
- [REFACTOR.md](REFACTOR.md) - v2.0 architecture plan
- [HANDOFF.md](HANDOFF.md) - Development handoff guide

---

## Roadmap

- [x] Phase 1: GitHub cleanup
- [x] Phase 2: Core infrastructure
- [x] Phase 3: Generation pipeline
- [x] Phase 4: Agent rebuild (10 agents)
- [x] Phase 5: API completion (streaming, temporal, models)
- [x] Phase 6: Testing & documentation
- [x] Phase 7: Deployment & production
- [x] Phase 8-17: Rate limiting, parallelism, model validation
- [x] Phase 18: Character interactions (chat, dialog, survey)

---

## License

MIT License - see LICENSE file for details.

---

**Built with** FastAPI | LangGraph | Google Gemini | Pydantic | SQLAlchemy

**v2.0 Status**: Complete - Ready for Production
