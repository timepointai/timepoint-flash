# TIMEPOINT Flash

**AI-powered photorealistic time travel - batteries included.**

Generate historically accurate scenes from any moment in history using AI multi-agent workflows powered by Google Gemini models.

**[📘 For AI Agents: See AGENTS.md](AGENTS.md)** | **[🚀 Quick Start: See QUICKSTART.md](QUICKSTART.md)**

---

## What You Get

✨ **CLI Tool** - `tp demo` and see results in 90 seconds
🖼️ **Web Gallery** - HTMX-powered UI, zero build step
🗄️ **SQLite Auto-Deploy** - No database setup required
🍌 **Nano Banana** - Latest Google Gemini image models (2.5 + Pro)
🤖 **11-Agent Workflow** - LangGraph orchestration
📡 **Public API** - No authentication, ready-to-use examples
🧪 **Comprehensive Tests** - Fast unit + e2e with LLM judge

---

## Quick Start

```bash
# One command setup (checks Python, installs deps, configures API key)
./setup.sh

# Run demo (generates 3 scenes + opens gallery)
./tp demo
```

That's it! See [QUICKSTART.md](QUICKSTART.md) for details.

---

## Public API Access

**No authentication required.** Just start the server and access the API from any client.

```bash
# Start server
./tp serve

# From another terminal or any HTTP client:
curl -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{"input_query": "Ancient Rome, 50 BCE"}'

# Get all results
curl http://localhost:8000/api/feed | jq '.'
```

### Ready-to-Run Examples

We've included working code in multiple languages:

```bash
cd examples/

# Python - Complete client
python3 python_client.py

# Python - SSE streaming
python3 stream_progress.py

# JavaScript/Node.js
npm install && node javascript_client.js

# Bash/curl
./curl_examples.sh
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/timepoint/create` | POST | Generate a new timepoint |
| `/api/timepoint/status/{session_id}` | GET | Stream progress (SSE) |
| `/api/timepoint/details/{slug}` | GET | Get complete data |
| `/api/feed` | GET | List all timepoints |

**[📖 Full API Documentation →](docs/API.md)**

### Rate Limiting

- **Email-based**: 1 generation/hour per email
- **IP-based**: 10 generations/hour for anonymous
- **Trusted hosts**: Unlimited (replit.dev, your domain)

---

## CLI Commands

```bash
./tp generate "Medieval marketplace, London 1250"  # Generate scene
./tp list                                          # List all timepoints
./tp serve --open-browser                          # Start server + gallery
./tp demo                                          # Quick demo mode
```

---

## Features

### 🎬 Multi-Agent Orchestration

11 specialized AI agents work together via LangGraph:

```
Query → Judge → Timeline → Scene → Characters → Moment
  → Dialog → Camera → Graph → Image Prompt → Image Gen → Segmentation
```

Each agent uses Google Gemini models for different tasks:
- **gemini-1.5-flash** - Fast validation and logic
- **gemini-1.5-pro** - Creative scene generation
- **Nano Banana** (gemini-2.5-flash-image) - Photorealistic images ($0.039/image)
- **Nano Banana Pro** (gemini-3-pro-image) - 2K/4K, text rendering ($0.139+/image)

**[🍌 Learn more about Nano Banana models →](docs/MODELS.md)**

### 🖼️ Web Gallery

HTMX-powered UI with:
- Masonry grid layout
- Infinite scroll
- Live generation progress (SSE)
- Character & dialog display
- Zero JavaScript build step

### 🗄️ Database Support

**SQLite (default)**
- Works out of the box
- File-based: `sqlite:///./timepoint_local.db`
- In-memory: `sqlite:///:memory:` (for tests)

**PostgreSQL (optional)**
- For production deployments
- Set `DATABASE_URL=postgresql://...`
- Auto-detected and used when available

### 🧪 Testing

Smart database detection for tests:

```bash
./test.sh fast     # Unit tests (5s, no API calls)
./test.sh e2e      # Full workflow (5-10min, requires API key)
./test.sh all      # Everything

# Tests automatically use:
# - SQLite by default
# - PostgreSQL if DATABASE_URL is set and accessible
# - Fallback to in-memory SQLite if PostgreSQL unavailable
```

E2E tests include **LLM-based quality judge** that scores:
- Historical accuracy
- Character quality
- Dialog authenticity
- Scene coherence

---

## Tech Stack

**Backend**
- FastAPI 0.115+ (async Python web framework)
- Uvicorn (ASGI server)
- SQLAlchemy 2.0 (ORM, supports SQLite + PostgreSQL)
- Alembic (database migrations)

**AI & Orchestration**
- LangGraph (agent workflow)
- LangChain (LLM framework)
- Mirascope + Instructor (structured outputs)
- Google Generative AI SDK

**Frontend**
- HTMX 1.9 (dynamic UI, 14KB)
- Jinja2 (templates)
- Water.css (classless CSS)
- Server-Sent Events (real-time updates)

**CLI & Tools**
- Click (CLI framework)
- Rich (terminal formatting)
- HTTPX (async HTTP client)

**Image & Graph Processing**
- Pillow (image manipulation)
- NetworkX (scene graph)
- CairoSVG (SVG rendering)

---

## Project Structure

```
timepoint-flash/
├── app/
│   ├── agents/              # 11 LangGraph AI agents
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
│   │   └── scene_graph.py
│   ├── routers/             # API routes
│   │   ├── timepoint.py
│   │   ├── feed.py
│   │   └── gallery.py       # ← New: Web UI routes
│   ├── templates/           # ← New: Jinja2 templates
│   │   ├── base.html
│   │   ├── gallery.html
│   │   ├── viewer.html
│   │   └── generate.html
│   ├── static/              # ← New: CSS & assets
│   │   └── css/style.css
│   ├── cli.py               # ← New: CLI tool
│   ├── models.py            # Database models (SQLite + PostgreSQL)
│   ├── database.py
│   ├── config.py
│   ├── schemas.py
│   └── main.py
├── tests/
│   ├── conftest.py          # Smart database fixtures
│   ├── test_fast.py         # Unit tests
│   ├── test_e2e.py          # Integration tests
│   └── utils/llm_judge.py
├── pyproject.toml           # CLI entry point + dependencies
├── requirements.txt
├── .env.example
├── README.md
├── AGENTS.md
└── QUICKSTART.md            # ← New: Ultra-concise guide
```

---

## API Endpoints

### Gallery (Web UI)
- `GET /` → Gallery grid
- `GET /view/{slug}` → Single timepoint
- `GET /generate` → Live generation form
- `GET /demo` → Demo landing

### API (JSON)
- `POST /api/timepoint/create` → Start generation
- `GET /api/timepoint/status/{session_id}` → SSE progress stream
- `GET /api/timepoint/details/{slug}` → Get timepoint data
- `GET /api/feed` → List all (paginated)
- `GET /api/docs` → Interactive API documentation

---

## Environment Variables

Minimal `.env`:

```bash
# Required (choose one):
OPENROUTER_API_KEY=your_key      # Includes Google models
# OR
GOOGLE_API_KEY=your_key          # Direct Google AI access

# Optional:
DATABASE_URL=sqlite:///./timepoint_local.db  # Default
LOGFIRE_TOKEN=your_token         # Observability (optional)
DEBUG=true                       # Enable API docs
```

See `.env.example` for all options.

---

## Deployment

### Local Development
```bash
./tp serve --port 8000
```

### Docker
```bash
docker build -t timepoint-flash .
docker run -p 8000:8000 --env-file .env timepoint-flash
```

### Replit
Configured for one-click deployment - just import the repo.

### Railway / Render / Fly.io
1. Push to GitHub
2. Connect platform
3. Set environment variables
4. Deploy

**Note**: For production, set `DATABASE_URL` to PostgreSQL.

---

## Development

### Database Migrations
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

### Code Quality
```bash
ruff format .       # Format
mypy app/           # Type check
pytest -m fast      # Unit tests
```

### Adding New Agents
See [AGENTS.md](AGENTS.md) for architecture details.

---

## Configuration

### Rate Limiting
Default: 1 timepoint/hour per email

```bash
MAX_TIMEPOINTS_PER_HOUR=5  # Increase limit
```

### Models
```bash
JUDGE_MODEL=gemini-1.5-flash
CREATIVE_MODEL=gemini-1.5-pro
IMAGE_MODEL=google/gemini-2.5-flash-image
```

### CORS
```bash
ALLOWED_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
```

---

## Performance

Typical timepoint generation:
- **Judge**: 1-2s
- **Timeline**: 1-2s
- **Scene + Characters**: 3-5s
- **Moment + Dialog**: 3-5s
- **Camera + Graph**: 2-3s
- **Image Prompt**: 1s
- **Image Generation**: 25-35s (Gemini 2.5)
- **Segmentation**: 2-3s

**Total**: 40-60s end-to-end

---

## Documentation

- **[README.md](README.md)** - Overview (this file)
- **[QUICKSTART.md](QUICKSTART.md)** - Ultra-concise getting started
- **[docs/API.md](docs/API.md)** - Public API guide for developers
- **[docs/MODELS.md](docs/MODELS.md)** - Nano Banana models explained
- **[AGENTS.md](AGENTS.md)** - Technical docs for AI agents
- **[examples/](examples/)** - Ready-to-run code examples
- **[API Docs](http://localhost:8000/api/docs)** - Interactive Swagger UI

---

## License

MIT License - see LICENSE file for details.

---

**Built with** ⚡ FastAPI | 🧠 LangGraph | 🎨 Google Gemini | ⚡ HTMX
