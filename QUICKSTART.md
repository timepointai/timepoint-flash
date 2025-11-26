# TIMEPOINT Flash - Quick Start

**One command to photorealistic time travel.**

## Setup (One Command!)

```bash
./setup.sh
```

This automated script will:
- ✅ Check Python version (3.11+ required)
- ✅ Install all dependencies (using uv or pip)
- ✅ Create .env from template
- ✅ Prompt for your OpenRouter API key
- ✅ Validate everything works

Get a free API key at [openrouter.ai](https://openrouter.ai/keys)

## Run Demo

```bash
./tp demo
```

This generates 3 sample scenes, starts the server, and opens the gallery in your browser.

## CLI Commands

```bash
./tp generate "Medieval marketplace, London 1250"   # Generate a scene
./tp list                                           # List all timepoints
./tp serve --open-browser                           # Start gallery server
./tp demo                                           # Quick demo mode
```

## What's Happening?

1. **11 AI agents** orchestrate via LangGraph
2. **Google Gemini models** generate scenes + images
3. **SQLite database** stores everything (auto-created)
4. **Web gallery** displays results with HTMX

## Next Steps

- **Browse gallery**: Visit `http://localhost:8000`
- **Generate custom scene**: Click "Generate" in the UI
- **Read full docs**: See [README.md](README.md) for architecture details
- **API docs**: `http://localhost:8000/api/docs`

## Troubleshooting

**"No API key found"**: Run `./setup.sh` to configure interactively, or manually edit `.env`

**"Port already in use"**: Add `--port 8001` to change port (default is 8000)

**"Missing packages"**: Run `./setup.sh` or `uv sync` (or `pip install -e .`)

**"Tests failing"**: Run `./test.sh fast` for unit tests (no API calls needed)

---

**Total time**: ~60 seconds per scene generation | **Storage**: SQLite file | **Dependencies**: Python 3.11+

For production deployment, architecture details, and agent documentation, see [README.md](README.md) and [AGENTS.md](AGENTS.md).
