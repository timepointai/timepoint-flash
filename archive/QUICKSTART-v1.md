# TIMEPOINT Flash - Quick Start

**One command to photorealistic time travel.**

## Setup (One Command!)

```bash
./setup.sh
```

**Time**: ~30 seconds

This automated script will:
- ✅ Check Python version (3.11+ required)
- ✅ Install all dependencies (using uv or pip)
- ✅ Create .env from template
- ✅ Prompt for your OpenRouter API key
- ✅ Validate everything works

Get a free API key at [openrouter.ai](https://openrouter.ai/keys)

### Expected Output

```
================================================
🎬 TIMEPOINT FLASH - Setup
================================================

[1/6] Checking Python version...
✓ Python 3.14.0

[2/6] Installing dependencies...
Using uv for fast installation...
✓ Dependencies installed with uv

[3/6] Configuring environment...
✓ Created .env from template

⚠ OPENROUTER_API_KEY not configured

To use TIMEPOINT Flash, you need an OpenRouter API key.
Get a free key at: https://openrouter.ai/keys

Enter your OpenRouter API key (or press Enter to skip): sk-or-v1-xxxxx
✓ API key saved to .env

[4/6] Setting up CLI tool...
✓ CLI tool ready

[5/6] Validating installation...
✓ CLI working correctly

[6/6] Setup complete!

================================================
✨ TIMEPOINT Flash is ready!
================================================

✓ OpenRouter API key configured

Try the demo:
  ./tp demo

Or generate a custom scene:
  ./tp generate "Medieval marketplace, London 1250"
```

**Next**: Run `./tp demo`

## Run Demo

```bash
./tp demo
```

**Time**: ~60 seconds for generation (+ 1-2 minutes per scene to complete)

This generates 3 sample scenes, starts the server, and opens the gallery in your browser.

### Expected Output

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 🎬 TIMEPOINT FLASH - Demo Mode                              ┃
┃                                                              ┃
┃ Generating 3 stunning historical scenes...                  ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Generating 3 demo timepoint(s)...

[1/3] Medieval marketplace in London, winter 1250
  ✓ Started generation

[2/3] Ancient Rome forum, summer 50 BCE
  ✓ Started generation

[3/3] American Revolutionary War, Valley Forge 1777
  ✓ Started generation

⏳ Generation in progress (takes ~1-2 minutes each)...
You can watch the progress in the gallery!

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Opening gallery in browser...                               ┃
┃                                                              ┃
┃ http://localhost:8000                                        ┃
┃                                                              ┃
┃ The server will keep running. Press Ctrl+C to stop.         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

Server is running. View the gallery in your browser.
Press Ctrl+C to stop the server.
```

**Your browser automatically opens to**: `http://localhost:8000`

### What You'll See in the Gallery

1. **Gallery Homepage**: Grid of timepoint cards (initially empty, filling in as scenes generate)
2. **Real-time Updates**: Watch scenes appear as they complete (~60s each)
3. **Click any card**: See full details, characters, dialog, and high-res image
4. **Generate button**: Create your own custom scenes

### While Demo Runs

**Server logs show**:
- Judge validation (1-2s)
- Timeline extraction (1-2s)
- Scene building (3-5s)
- Character creation (2-3s)
- Dialog generation (2-3s)
- Image generation (30-40s) ← longest step
- Segmentation (2-3s)
- **Total**: ~40-60s per scene

**Gallery auto-refreshes** as scenes complete. You'll see progress bars and status updates.

## CLI Commands

```bash
./tp generate "Medieval marketplace, London 1250"   # Generate a scene
./tp list                                           # List all timepoints
./tp serve --open-browser                           # Start gallery server
./tp demo                                           # Quick demo mode
```

## Public API (No Auth!)

**Just start the server and access from any client:**

```bash
# Terminal 1: Start server
./tp serve
```

**Your server is now running at**: `http://localhost:8000`

**View API docs**: `http://localhost:8000/api/docs` (interactive Swagger UI)

### Using the API

From another terminal (or any HTTP client):

```bash
# Generate from curl:
curl -X POST http://localhost:8000/api/timepoint/create \
  -H "Content-Type: application/json" \
  -d '{"input_query": "Ancient Rome, 50 BCE"}'
```

### Ready-to-Run Examples

**IMPORTANT**: Make sure `./tp serve` is running first!

```bash
# Terminal 2: Run examples
cd examples/

python3 python_client.py      # Complete Python client
python3 stream_progress.py    # Real-time SSE streaming
./curl_examples.sh            # Bash/curl examples
```

**See**: [examples/README.md](examples/README.md) for details on each example.

**[📖 Full API Documentation →](docs/API.md)**

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
