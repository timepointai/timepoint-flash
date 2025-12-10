# TIMEPOINT Flash v2.2.1

**TL;DR**: Type a historical moment, get a fully-realized scene with characters, dialog, relationships, and an AI-generated image.

```
"signing of the declaration of independence"
         ↓ 15 AI agents ↓
Scene + 8 Characters + Dialog + Relationships + Image
```

---

## What It Does

Give TIMEPOINT Flash a natural language query and it generates:

| Output | Example |
|--------|---------|
| **When** | July 4, 1776, afternoon, summer |
| **Where** | Independence Hall, Philadelphia |
| **Who** | 8 characters with bios, roles, appearances |
| **What** | Scene description, atmosphere, tension |
| **Dialog** | 7 period-appropriate lines |
| **Relationships** | Who knows whom, alliances, rivalries |
| **Image** | Photorealistic AI-generated scene |

Then **chat with the characters**, extend the dialog, or survey them all with questions.

## Quick Start

```bash
# 1. Clone & install
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash
pip install -e .

# 2. Set API key
export GOOGLE_API_KEY="your-key"  # or OPENROUTER_API_KEY

# 3. Run the demo (easiest)
./demo.sh
```

The interactive demo lets you generate timepoints, browse results, chat with characters, and more - no curl commands needed.

### Or Use the API Directly

```bash
# Start server
uvicorn app.main:app --reload

# Generate a timepoint
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence"}'
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

### 15 Specialized Agents

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

- **Google AI** - Gemini 2.5 Flash (text), Gemini 2.5 Flash Image (generation)
- **OpenRouter** - 300+ models including Claude 4.5, Sonnet 4, GPT-4o

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
CREATIVE_MODEL=gemini-2.5-flash
IMAGE_MODEL=gemini-2.5-flash-image
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

- 514 tests
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
│   ├── agents/              # 15 agent implementations
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
- [docs/AGENTS.md](docs/AGENTS.md) - Multi-agent architecture explained
- [docs/API.md](docs/API.md) - Complete API reference
- [docs/TEMPORAL.md](docs/TEMPORAL.md) - Temporal navigation guide
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guide
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

Apache License 2.0 - see LICENSE and NOTICE files for details.

---

**Built with** FastAPI | LangGraph | Google Gemini | Pydantic | SQLAlchemy

**v2.2.1** | Production Ready | [API Docs](http://localhost:8000/docs)
