# TIMEPOINT Flash

Type any moment in history. Get a fully-realized scene you can explore.

```
> "assassination of julius caesar"
```

**2 minutes later:**

```
March 15, 44 BCE - The Ides of March
Theatre of Pompey, Rome

CHARACTERS:
- Julius Caesar - Dictator of Rome, 55, purple-trimmed toga
- Marcus Brutus - Senator and conspirator, 41, conflicted expression
- Gaius Cassius - Mastermind of the plot, 42, cold determination
- Mark Antony - Caesar's loyal ally, 39, unaware of the danger
- Decimus Brutus - Trusted friend turned betrayer, 43
...and 3 more

DIALOG:
Caesar: "What is this? Why do you press upon me so?"
Casca: "Speak, hands, for me!" *strikes first*
Brutus: "Et tu, Brute?"
Caesar: *falls* "Then fall, Caesar..."

RELATIONSHIPS:
- Brutus ↔ Caesar: Surrogate father/son, now betrayer
- Cassius → Brutus: Manipulator, exploited his honor
- Antony → Caesar: Fierce loyalty, will seek vengeance
```

Plus an AI-generated image of the scene, and you can **chat with any character**:

```
> You: "Brutus, do you regret what you've done?"

Brutus: "Regret? Every fiber of my being screams with it. But Rome...
Rome demanded this sacrifice. I loved Caesar, but I loved Rome more.
History will judge whether I chose wisely. I fear it will not be kind."
```

---

## Try It (5 minutes)

```bash
# 1. Clone and install
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash
pip install -e .

# 2. Add your API key
cp .env.example .env
# Edit .env → add GOOGLE_API_KEY (get one at https://aistudio.google.com)

# 3. Start the server
./run.sh -r

# 4. In another terminal, run the demo
./demo.sh
```

The demo walks you through everything. Pick a historical moment, watch it generate, then chat with the characters.

---

## What Can You Do?

**Generate scenes** from any query:
- `"moon landing 1969"`
- `"last supper"`
- `"cleopatra meets caesar"`
- `"boston tea party"`
- `"beethoven's final concert"`

**Chat with characters** - ask them anything, they respond in-character with period-appropriate knowledge

**Extend the story** - generate more dialog, or jump forward/backward in time:
```bash
# One hour after Caesar's death...
POST /api/v1/temporal/{id}/next {"units": 1, "unit": "hour"}
```

**Survey everyone** - ask all characters the same question, get their perspectives:
```
"What do you fear most right now?"

Caesar: "I fear nothing. I am Caesar."
Brutus: "That Rome will not understand..."
Cassius: "That Antony will rally the mob..."
```

---

## How It Works

15 AI agents collaborate to build each scene:

1. **Validate** your query (is it historical? specific enough?)
2. **Extract** the date, location, time of day
3. **Research** who was there, what was happening
4. **Generate** 8 detailed characters with bios
5. **Map** their relationships (allies, enemies, tensions)
6. **Write** period-appropriate dialog
7. **Compose** the visual scene
8. **Generate** a photorealistic image

Each step streams progress in real-time. The whole process takes 1-4 minutes depending on settings.

---

## API

Everything in the demo is available via REST API:

```bash
# Generate a scene
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence", "generate_image": true}'

# Chat with a character
curl -X POST http://localhost:8000/api/v1/interactions/{id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character": "Benjamin Franklin", "message": "What do you think of this document?"}'
```

Interactive API docs at `http://localhost:8000/docs`

Full reference: [docs/API.md](docs/API.md)

---

## Configuration

Get a free API key from [Google AI Studio](https://aistudio.google.com) or [OpenRouter](https://openrouter.ai).

```bash
# .env
GOOGLE_API_KEY=your-key        # Required (or OPENROUTER_API_KEY)
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db  # Default, just works
```

Quality presets in the demo:

| Preset | Speed | Best For |
|--------|-------|----------|
| **Hyper** | ~1-2 min | Quick exploration |
| **Balanced** | ~2-4 min | Good quality |
| **HD** | ~4-6 min | Best results |

---

## Learn More

- [API Reference](docs/API.md) - Full endpoint documentation
- [Time Travel](docs/TEMPORAL.md) - Navigate forward/backward through history
- [Architecture](docs/AGENTS.md) - How the multi-agent pipeline works

---

## License

Apache 2.0

---

**Built with** Python, FastAPI, Google Gemini
