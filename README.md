# TIMEPOINT Flash API

**AI-powered photorealistic time travel API using Google Gemini 2.5 Flash Image models.**

Generate historically accurate scenes from any moment in history with AI-orchestrated multi-agent workflows, powered by LangGraph and Google's Generative AI suite.

---

## Features

- **Photorealistic Image Generation**: Using Google Gemini 2.5 Flash Image
- **Multi-Agent Orchestration**: LangGraph coordinates AI agents for scene building
- **Historical Accuracy**: Period-appropriate characters, dialog, and settings
- **Real-time Progress**: Server-Sent Events (SSE) for live generation updates
- **FastAPI Backend**: Modern async Python web framework
- **PostgreSQL Database**: Robust data persistence with SQLAlchemy ORM
- **Rate Limiting**: Built-in protection (configurable)
- **API Documentation**: Auto-generated OpenAPI docs

---

## Tech Stack

- **Framework**: FastAPI 0.115+
- **AI Orchestration**: LangGraph, LangChain
- **Models**:
  - `gemini-1.5-flash` (fast logic/validation)
  - `gemini-1.5-pro` (creative generation)
  - `google/gemini-2.5-flash-image` (image generation)
- **Database**: PostgreSQL + SQLAlchemy 2.0
- **Image Processing**: Pillow, CairoSVG
- **Graph Analysis**: NetworkX
- **Observability**: Logfire (optional)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Google AI API key (get from [Google AI Studio](https://makersuite.google.com/app/apikey))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/realityinspector/timepoint-flash.git
   cd timepoint-flash
   ```

2. **Run setup script**
   ```bash
   chmod +x init.sh
   ./init.sh
   ```

3. **Activate virtual environment**
   ```bash
   source .venv/bin/activate
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database URL
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the server**
   ```bash
   uvicorn app.main:app --reload
   ```

   API will be available at: http://localhost:5000

   API docs at: http://localhost:5000/api/docs

---

## Environment Variables

Create a `.env` file with the following:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/timepoint_flash

# Google AI (Primary)
GOOGLE_API_KEY=your_google_api_key_here

# OpenRouter (Fallback)
OPENROUTER_API_KEY=optional_fallback_key

# Observability
LOGFIRE_TOKEN=optional_token

# Application Settings
DEBUG=false
MAX_TIMEPOINTS_PER_HOUR=1
JUDGE_MODEL=gemini-1.5-flash
IMAGE_MODEL=google/gemini-2.5-flash-image

# Security (Generate with: openssl rand -hex 32)
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
ALLOWED_ORIGINS=["http://localhost:3000"]
```

---

## API Endpoints

### Health Check
```
GET /health
```
Returns service status.

### Create Timepoint
```
POST /api/timepoint/create
Body: { "query": "medieval marketplace in winter 1250", "email": "user@example.com" }
```
Starts timepoint generation, returns session ID.

### Stream Progress (SSE)
```
GET /api/timepoint/status/{session_id}
```
Real-time progress updates via Server-Sent Events.

### Get Timepoint Details
```
GET /api/timepoint/details/{year}/{season}/{slug}
```
Returns full timepoint data (characters, dialog, images, etc.).

### Feed/Gallery
```
GET /api/feed?page=1&limit=50
```
List all timepoints with pagination.

### Full API Documentation
Visit `/api/docs` when running the server for interactive Swagger UI.

---

## Architecture

### AI Agent Workflow

```
User Query
    ↓
[JUDGE] Validate & clean input
    ↓
[TIMELINE] Extract year, season, location
    ↓
[SCENE] Build setting, weather, environment
    ↓
[CHARACTERS] Generate 3-12 unique characters
    ↓
[MOMENT] Create dramatic plot/interaction
    ↓
[DIALOG] Generate period-accurate conversations
    ↓
[CAMERA] Define cinematic camera angles
    ↓
[GRAPH] Build NetworkX scene graph
    ↓
[IMAGE_PROMPT] Compile comprehensive prompt
    ↓
[IMAGE_GENERATION] Generate image (Gemini 2.5 Flash)
    ↓
[SEGMENTATION] Label characters in image
    ↓
Save to Database
```

### Project Structure

```
timepoint-flash/
├── app/
│   ├── agents/              # LangGraph AI agents
│   │   ├── judge.py
│   │   ├── timeline.py
│   │   ├── scene_builder.py
│   │   ├── characters.py
│   │   ├── moment.py
│   │   ├── dialog.py
│   │   ├── camera.py
│   │   └── graph_orchestrator.py
│   ├── services/            # External integrations
│   │   ├── google_ai.py
│   │   ├── openrouter.py
│   │   ├── openrouter_fallback.py
│   │   └── scene_graph.py
│   ├── routers/             # API endpoints
│   │   ├── timepoint.py
│   │   ├── feed.py
│   │   └── email.py
│   ├── utils/
│   │   └── rate_limiter.py
│   ├── models.py            # SQLAlchemy ORM models
│   ├── database.py          # Database setup
│   ├── config.py            # Pydantic settings
│   ├── schemas.py           # Pydantic request/response models
│   └── main.py              # FastAPI app entry point
├── alembic/                 # Database migrations
├── scripts/                 # Utility scripts
├── .env.example             # Environment template
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container config
├── .replit                  # Replit deployment config
└── pyproject.toml           # Project metadata
```

---

## Deployment

### Replit

This repo is configured for Replit deployment. Simply:
1. Import repo to Replit
2. Set environment secrets in Replit
3. Run with the `.replit` configuration

### Docker

```bash
docker build -t timepoint-flash .
docker run -p 5000:5000 --env-file .env timepoint-flash
```

### Railway / Cloud Platforms

1. Push to GitHub
2. Connect to Railway/Render/Fly.io
3. Set environment variables
4. Deploy

---

## Development

### Testing

Timepoint Flash includes a comprehensive test suite with both fast unit tests and full end-to-end integration tests with LLM-based quality assessment.

#### Quick Start

```bash
# Fast unit tests (no API key required)
./test.sh fast

# Full e2e tests with LLM judge (requires OPENROUTER_API_KEY)
export OPENROUTER_API_KEY="your-key-here"
./test.sh e2e

# All tests
./test.sh all

# With coverage report
./test.sh coverage
```

#### Test Setup

1. **Install test dependencies**:
   ```bash
   pip install -e ".[dev]"
   ```

2. **Set up environment**:
   ```bash
   # Option 1: Export environment variable
   export OPENROUTER_API_KEY="your-openrouter-api-key"

   # Option 2: Create .env.dev file
   cp .env.dev.example .env.dev
   # Edit .env.dev with your API key
   ```

3. **Run tests**:
   ```bash
   # Fast tests only (no external API calls)
   pytest -m fast

   # E2E tests only (requires API key)
   pytest -m e2e

   # All tests
   pytest

   # With verbose output
   pytest -v -s
   ```

#### Test Types

**Fast Tests** (`tests/test_fast.py`)
- Unit tests for database models
- Rate limiting logic
- API endpoint structure
- No external API calls
- Run in ~5 seconds

**E2E Tests** (`tests/test_e2e.py`)
- Full timepoint generation workflow
- LLM-based quality assessment
- Real API calls to OpenRouter/Google
- Tests historical scenarios
- Run in ~5-10 minutes

#### LLM Performance Judge

The e2e tests include an LLM-based judge that evaluates:
- **Historical Accuracy** (0-100): Period-appropriate elements
- **Character Quality** (0-100): Character development and consistency
- **Dialog Quality** (0-100): Natural, period-appropriate dialog
- **Scene Coherence** (0-100): Overall scene consistency

Example output:
```
QUALITY ASSESSMENT RESULTS
========================================
Overall Score:        76.5/100
Historical Accuracy:  82.0/100
Character Quality:    78.0/100
Dialog Quality:       72.0/100
Scene Coherence:      75.0/100

Feedback: Strong historical accuracy with well-developed
characters. Dialog could be more period-specific.
========================================
Status: ✅ PASSED
```

#### Test Configuration

Test settings in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
markers = [
    "fast: Fast unit tests (no external API calls)",
    "e2e: End-to-end integration tests (requires API keys)",
    "slow: Slow tests (long-running operations)",
]
timeout = 300
```

### Code Quality

```bash
# Format with ruff
ruff format .

# Type checking
mypy app/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Rate Limiting

Default: 1 timepoint per hour per email address.

Configure in `.env`:
```bash
MAX_TIMEPOINTS_PER_HOUR=1
```

---

## Observability

Optional Logfire integration for monitoring:

1. Get token from [Logfire](https://logfire.pydantic.dev/)
2. Set `LOGFIRE_TOKEN` in `.env`
3. View traces and metrics in Logfire dashboard

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

---

## License

MIT License - see LICENSE file for details.

---

## Support

For issues or questions, please open an issue on GitHub.

---

**Built with** ⚡ **FastAPI** | 🧠 **LangGraph** | 🎨 **Google Gemini**
