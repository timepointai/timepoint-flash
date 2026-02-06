# TIMEPOINT Flash

Generate historically grounded, AI-illustrated scenes from any moment in history. Type a query, get back a complete scene: characters with distinct voices, period-accurate dialog, relationship dynamics, and a photorealistic image — all verified against Google Search.

```bash
curl -X POST localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "AlphaGo plays Move 37 against Lee Sedol, Seoul March 2016", "generate_image": true}'
```

**What comes back:**

```
Location:   Four Seasons Hotel, Seoul, South Korea
Date:       2016-03-10, afternoon
Tension:    high

Characters:
  Lee Sedol [primary] — short, halting fragments, stunned understatement
  Commentator 1 [secondary] — chatty, analytical, comfortable on-air cadence
  AlphaGo [primary, silent] — represented by monitor (non-human entity)

Dialog:
  Lee Sedol: "...Huh. That's... certainly a move."
  Commentator: "It's either genius or madness, and I honestly can't tell which."
  Lee Sedol: "It's... unexpected, to say the least."

+ AI-generated photorealistic image of the scene
```

Then interrogate the characters:

```
> You: "Lee Sedol, what went through your mind when you saw Move 37?"
```

Or jump forward in time:

```bash
POST /api/v1/temporal/{id}/next {"units": 1, "unit": "hour"}
# → One hour later: Lee Sedol has left the room. The commentators are still trying to explain it.
```

---

## Quick Start

**Prerequisites:** Python 3.10+ and a Google API key ([free at AI Studio](https://aistudio.google.com))

```bash
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash
./setup.sh            # Checks prereqs, installs deps, creates .env
# Edit .env → add your GOOGLE_API_KEY
./quickstart.sh       # Starts server + generates a demo scene
```

Or manually:

```bash
pip install -e .
cp .env.example .env  # Add your API key
./run.sh -r           # Start server
./demo.sh             # Interactive demo with 10 templates
```

Swagger docs at `http://localhost:8000/docs`

---

## How It Works

15 specialized agents run a pipeline with parallel execution, Google Search grounding, and a critique-retry loop:

```
Judge → Timeline → Grounding (Google Search) → Scene
                                                  ↓
                          Characters (grounded) + Moment + Camera  [parallel]
                                                  ↓
                                    Dialog → Critique (auto-retry if issues)
                                                  ↓
                                   ImagePrompt → Optimizer → ImageGen
```

**Key capabilities:**

- **Google Search grounding** — Verified locations, dates, participants. Not "a room in New York" but "35th floor of the Equitable Center, Manhattan."
- **Critique loop** — Dialog is reviewed for anachronisms, cultural errors (Greek vs Roman deities), modern idioms, and voice distinctiveness. Auto-retries with corrections if critical issues found.
- **Voice differentiation** — Each character gets a social register (elite/educated/common/servant/child) that constrains sentence structure, vocabulary, and verbal tics. Characters must be identifiable by voice alone.
- **Emotional transfer** — The image prompt optimizer translates narrative tension into physicalized body language instead of discarding it. "Climactic tension" becomes "wide eyes, dropped objects, body recoiling."
- **Entity representation** — Non-human entities (Deep Blue, AlphaGo, HAL 9000) are shown through their physical representatives (IBM operator, monitor display, red camera lens).
- **Anachronism prevention** — Era-specific exclusion lists, mutual exclusion rules (Roman toga + tricorn hat), famous painting drift detection.
- **3-tier image fallback** — Google Imagen → OpenRouter Flux → Pollinations.ai. Image generation never fails.

---

## Example Scenes

**Vesuvius erupts as seen from a Pompeii bakery, 79 AD:**

```
Location: Pompeii, Italy - bakery near the Vesuvius gate
Characters: Marcus (baker), Lucius, Fortunata, Slave Boy
Dialog:
  Marcus: "By Jupiter, what was that sound? Is that...ash falling from the sky?"
```

**Mission Control, the moment Eagle lands on the Moon:**

```
Location: Mission Control, Johnson Space Center, Houston, Texas
Characters: Charlie Duke (CAPCOM), Gene Kranz (Flight Director)
Dialog:
  Charlie Duke: "Roger, Tranquility Base here, the Eagle has landed."
  Gene Kranz: "Okay, Tranquility Base. We copy you down. Houston is a go."
```

**Gavrilo Princip at Schiller's Deli, Sarajevo 1914:**

```
Location: Moritz Schiller's Delicatessen near the Latin Bridge over the Miljacka River
Characters: Gavrilo Princip, Archduke Franz Ferdinand, Sophie Chotek
Tension: high — the car took a wrong turn and stopped right in front of him
```

Each scene includes full character bios, relationship graphs, scene metadata, camera composition, and a generated image.

---

## Quality Presets

| Preset | Speed | Provider | Best For |
|--------|-------|----------|----------|
| **hyper** | ~55s | OpenRouter | Fast iteration, prototyping |
| **balanced** | ~90-110s | Google Native | Production quality |
| **hd** | ~2-2.5 min | Google Native | Maximum fidelity (extended thinking) |
| **gemini3** | ~60s | OpenRouter | Latest model, agentic workflows |

```bash
# Hyper for speed
curl -X POST localhost:8000/api/v1/timepoints/generate/stream \
  -d '{"query": "moon landing 1969", "preset": "hyper", "generate_image": true}'

# HD for quality
curl -X POST localhost:8000/api/v1/timepoints/generate/stream \
  -d '{"query": "moon landing 1969", "preset": "hd", "generate_image": true}'
```

---

## API

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/timepoints/generate/stream` | Generate scene with SSE progress (recommended) |
| `POST /api/v1/timepoints/generate/sync` | Generate scene, block until complete |
| `POST /api/v1/timepoints/generate` | Background generation, poll for result |
| `GET /api/v1/timepoints/{id}` | Retrieve a completed scene |
| `POST /api/v1/interactions/{id}/chat` | Chat with a character |
| `POST /api/v1/temporal/{id}/next` | Jump forward in time |
| `POST /api/v1/temporal/{id}/prior` | Jump backward in time |
| `GET /api/v1/temporal/{id}/sequence` | Get linked timeline |
| `POST /api/v1/eval/compare` | Compare model latencies |
| `GET /api/v1/models/free` | List free OpenRouter models |

Full reference: [docs/API.md](docs/API.md)

---

## Configuration

```bash
# .env
GOOGLE_API_KEY=your-key                              # Required (free at aistudio.google.com)
OPENROUTER_API_KEY=your-key                          # Optional (for hyper/gemini3 presets)
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db      # Default storage
```

---

## Testing

```bash
python3.10 -m pytest tests/unit/ -v         # 402 unit tests
python3.10 -m pytest tests/integration/ -v  # 81 integration tests
python3.10 -m pytest tests/e2e/ -v          # 13 end-to-end tests
```

496 tests covering generation, character interactions, temporal navigation, image fallback, historical grounding, schema validation, and provider failover.

---

## Documentation

- [API Reference](docs/API.md) — Full endpoint documentation
- [Agent Architecture](docs/AGENTS.md) — Pipeline breakdown with example output
- [Temporal Navigation](docs/TEMPORAL.md) — Time travel mechanics
- [Eval Roadmap](docs/EVAL_ROADMAP.md) — Quality scoring and benchmark plans

---

## License

Apache 2.0

---

Built with Python, FastAPI, and Google Gemini. Part of [Timepoint AI](https://x.com/seanmcdonaldxyz).
