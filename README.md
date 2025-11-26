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

## 🚀 Zero to Demo in 90 Seconds

**The absolute laziest path** (2 commands):

```bash
# 1. Setup (30 seconds - installs deps, prompts for API key)
./setup.sh

# 2. Demo (60 seconds - generates 3 scenes, opens gallery in browser)
./tp demo
```

That's it! Your browser will open to `http://localhost:8000` showing the gallery.

**Even lazier?** Clone and run in one line:
```bash
git clone https://github.com/yourusername/timepoint-flash.git && cd timepoint-flash && ./setup.sh && ./tp demo
```

**What happens:**
- ✅ Setup validates Python 3.11+, installs dependencies
- ✅ Demo generates 3 stunning historical scenes
- ✅ Gallery opens automatically in your browser
- ✅ Server keeps running - watch scenes appear in real-time

**See:** [QUICKSTART.md](QUICKSTART.md) for step-by-step details with expected output.

---

## Quick Start (Detailed)

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
- **Nano Banana Pro** (gemini-3-pro-image) - **RECOMMENDED** 2K/4K, text rendering ($0.00012/image via OpenRouter!)
- **Nano Banana** (gemini-2.5-flash-image) - Standard quality ($0.001238/image)

**[🍌 Learn more about Nano Banana models →](docs/MODELS.md)** - Pro is cheaper AND better!



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

Comprehensive test suite with 40+ tests:

```bash
./test.sh fast     # Unit tests (~5s, no API calls)
./test.sh e2e      # Full workflow (~10-15min, requires API key)
./test.sh all      # Everything
./test.sh coverage # Generate coverage report

# Tests automatically use:
# - SQLite by default
# - PostgreSQL if DATABASE_URL is set and accessible
# - Fallback to in-memory SQLite if PostgreSQL unavailable
```

**Test Categories**:
- **13 fast unit tests** - Database, API, rate limiting
- **10 e2e scenarios** - Full workflow with LLM judge evaluation
- **8 agent tests** - Individual agent validation
- **3 image tests** - Image generation & segmentation
- **8 API tests** - Rate limiting, concurrency, error handling

**Features**:
- Smart polling (no hardcoded waits)
- Auto-retry on transient failures
- Test isolation with automatic cleanup
- Mock mode for offline testing (`USE_MOCKS=true`)
- LLM-based quality judge (evaluates historical accuracy, character quality, dialog, coherence)
- CI/CD integration with GitHub Actions

**[📖 Full Testing Guide →](TESTING.md)**

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
IMAGE_MODEL=google/gemini-3-pro-image-preview  # Nano Banana Pro (recommended)
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
- **[TESTING.md](TESTING.md)** - Comprehensive testing guide
- **[docs/API.md](docs/API.md)** - Public API guide for developers
- **[docs/MODELS.md](docs/MODELS.md)** - Nano Banana models explained
- **[AGENTS.md](AGENTS.md)** - Technical docs for AI agents
- **[examples/](examples/)** - Ready-to-run code examples
- **[API Docs](http://localhost:8000/api/docs)** - Interactive Swagger UI

---

## Common Issues (Troubleshooting)

### "Python version too old"
**Solution**: Install Python 3.11+ from [python.org](https://www.python.org/downloads/)
```bash
python3 --version  # Should show 3.11 or higher
```

### "No API key found" or "OPENROUTER_API_KEY not configured"
**Solution 1**: Run setup script interactively:
```bash
./setup.sh  # Will prompt for API key
```

**Solution 2**: Manual edit:
```bash
echo "OPENROUTER_API_KEY=your_key_here" >> .env
# Get free key at: https://openrouter.ai/keys
```

### "Port already in use" (Address already in use: 8000)
**Solution**: Use a different port:
```bash
./tp serve --port 8001
# or
./tp demo --port 8001
```

### "Missing packages" or "ModuleNotFoundError"
**Solution**: Re-run setup or install manually:
```bash
./setup.sh  # Recommended

# OR manually:
uv sync           # If you have uv
pip install -e .  # Otherwise
```

### "Tests failing" or "Want to run tests"
**Fast tests** (no API key needed, ~5 seconds):
```bash
./test.sh fast
```

**E2E tests** (requires API key, ~10-15 minutes):
```bash
./test.sh e2e
```

See [TESTING.md](TESTING.md) for comprehensive testing guide.

### "Server not starting" or "Could not connect to API server"
**Check**:
1. Is another instance running? `lsof -i :8000` (kill if needed)
2. Are dependencies installed? Run `./setup.sh`
3. Is database accessible? Check `.env` for `DATABASE_URL`

**Solution**: Try manual start with debug output:
```bash
python3 -m uvicorn app.main:app --port 8000
```

### "Examples not working" (python_client.py, etc.)
**Solution**: Make sure server is running first:
```bash
# Terminal 1: Start server
./tp serve

# Terminal 2: Run example
cd examples/
python3 python_client.py
```

### "Images not generating" or "Generation takes forever"
**Typical timing**: 40-60 seconds per scene
- If taking >2 minutes, check API rate limits on OpenRouter
- Check server logs for errors
- Try with a simpler query: `./tp generate "Rome 50 BCE"`

### Still stuck?
1. Check [QUICKSTART.md](QUICKSTART.md) for detailed setup
2. Check [TESTING.md](TESTING.md) for test troubleshooting
3. Check server logs in terminal where you ran `./tp serve`
4. Open an issue on GitHub with error details

---

## License

MIT License - see LICENSE file for details.

---

**Built with** ⚡ FastAPI | 🧠 LangGraph | 🎨 Google Gemini | ⚡ HTMX
