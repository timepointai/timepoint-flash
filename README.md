# TIMEPOINT Flash

Dial into any moment in history. Twist the knobs to remix reality. Get a locked-in, photoreal scene ready to probe, prototype, or push boundaries.

```
> "assassination of julius caesar"
```

**Lock and load in under 2 minutes:**

```
March 15, 44 BCE - The Ides of March
Theatre of Pompey, Rome – Tension crackling like static in the air

CORE ELEMENTS:
- Julius Caesar: Dictator locked in the crosshairs, 55, purple-trimmed toga masking the storm
- Marcus Brutus: Senator flipping the script, 41, honor clashing with betrayal
- Gaius Cassius: Plot architect, 42, eyes like cold steel
- Mark Antony: Loyal wildcard, 39, one wrong move from unleashing hell
- Decimus Brutus: Inner-circle defector, 43, trust shattered
...plus 3 more shadows in the mix

DIALOG PULSE:
Caesar: "What is this? Why do you press upon me so?"
Casca: "Speak, hands, for me!" *strikes first*
Brutus: "Et tu, Brute?"
Caesar: *crumples* "Then fall, Caesar..."

RELATIONSHIP GRID:
- Brutus ↔ Caesar: Father-son bond wired for detonation
- Cassius → Brutus: Master manipulator hacking into ideals
- Antony → Caesar: Unbreakable alliance, primed for payback
```

Plus a hyper-real AI-rendered visual locked on the chaos. Now **interrogate the players**:

```
> You: "Brutus, do you regret what you've done?"

Brutus: "Regret, you ask? One does not regret performing a necessary duty for the Republic, however grievous the cost to one's own soul. My heart aches for the friend I lost, but my conscience stands firm for the liberty of Rome."
```

This is your rapid prototype deck for synthetic time travel – part of Timepoint AI's modular lab. Flash spins up scenes for web/app devs to test, tweak, and deploy. Pair it with Daedalus for heavy simulations or Clockchain for oracle-proof predictions.

---

## Gear Up and Launch (3 Minutes Flat)

```bash
# 1. Clone the rig
git clone https://github.com/timepoint-ai/timepoint-flash.git
cd timepoint-flash

# 2. One-command setup (checks prereqs, installs deps, creates .env)
./setup.sh

# 3. Add your API key
# Edit .env → plug in GOOGLE_API_KEY (grab one at https://aistudio.google.com)

# 4. See it in action (starts server + generates a demo)
./quickstart.sh
```

**Or the manual way:**

```bash
pip install -e .              # Install dependencies
cp .env.example .env          # Create config (add your API key)
./run.sh -r                   # Start server
./demo.sh                     # Interactive demo
```

Demo dashboard dials you in:

```
=== Main Menu ===
  1) Generate timepoint (sync) - Wait for full result
  2) Generate timepoint (streaming) - See live progress
  3) Generate from template
  4) SMART TEST - One-click Gemini 3 thinking + image (streaming)
  5) RAPID TEST FREE - One-click fastest free model + image
  6) Browse timepoints
  7) Health check
  8) API documentation
  9) Test endpoints
  10) Model Eval - Compare model performance
  --- Character Interactions ---
  11) Chat with character
  12) Extend dialog
  13) Survey characters
  q) Quit
```

**Power moves:**
- **SMART TEST**: Random template, Gemini 3 thinking model, instant image – deep reasoning on the fly.
- **Dial presets**: HD for pixel-perfect (~2 min), Balanced for flow (~90s), Hyper for velocity (~50s via OpenRouter).
- **Model selector**: Filter providers, hunt specifics, lock your weapon.
- **Free tier ops**: Tap OpenRouter's no-pay zone via `/api/v1/models/free` – quality king or speed demon.
- **10 locked templates**: Caesar takedown, Moon touchdown, Independence ink, Thermopylae stand, Berlin Wall breach, etc.
- **Player probes**: Chat deep, extend lines, survey perspectives.
- **Streaming API**: Use `/generate/stream` for real-time progress updates (recommended).

---

## What's Your Play?

**Prototype scenes** from raw input:
- `"moon landing 1969"` – Touchdown vibes, zero gravity.
- `"last supper"` – Table tension, shadows shifting.
- `"cleopatra meets caesar"` – Empire remix in progress.
- `"boston tea party"` – Rebellion brewing hot.
- `"beethoven's final concert"` – Symphony hits peak distortion.

**Probe characters** – Grill them on motives, futures, what-ifs. They stay in-code with era-locked intel.

**Shift timelines** – Crank forward or rewind:
```bash
# One hour post-Caesar reset...
POST /api/v1/temporal/{id}/next {"units": 1, "unit": "hour"}
```

**Scan the grid** – Hit every player with the same query, map their vectors:
```
"What do you fear most right now?"

Caesar: "My greatest concern is not for myself, but for the stability of Rome, and the treacherous hearts that might seek to unravel the peace I have forged."
Brutus: "That our Republic, forged by the spirit of liberty, becomes merely a name, subservient to the will of one man."
Cassius: "That the spirit of our Republic will be extinguished, replaced by the shadow of one man's boundless ambition."
```

---

## Under the Hood

16 specialized agents sync up like a well-oiled synthesizer:

1. **Lock query** – Validate for historical lock-on and precision.
2. **Pin coordinates** – Date, location, temporal pulse.
3. **Ground facts** – Google Search verification for historical accuracy.
4. **Map the field** – Who's in play, what's charging the air.
5. **Build profiles** – 8 wired characters with full specs.
6. **Grid connections** – Allies, rivals, live wires.
7. **Script the exchange** – Era-coded dialog that hits hard.
8. **Frame the shot** – Composition dialed for impact.
9. **Render visual** – Photoreal lock, no artifacts.

Streams hit your feed in real-time. Cycle time: 1-4 minutes, preset-dependent.

---

## Historical Accuracy

**Google Search Grounding** – Every historical query is verified against real sources:
- Exact venues and locations (not just "a room" but "35th floor of the Equitable Center, Manhattan")
- Verified dates and participants
- Period-accurate technology (CRT monitors in 1997, not flat screens)
- Physical presence detection (who was *actually* visible in photographs)

**Anachronism Prevention** – The system actively prevents:
- Wrong-era clothing (Roman togas vs French Revolutionary dress)
- Technology anachronisms (smartphones before 2007)
- Confused historical periods (WWI vs WWII equipment)
- Missing human operators (Deep Blue → IBM operator at the chess board)

**Entity Representation** – Non-human entities (computers, AI, organizations) are shown through their human representatives:
```
Deep Blue → IBM operator sitting across from Kasparov, making moves
The Government → The official who signed the document
HAL 9000 → Red camera lens on the wall
```

---

## API Lock-In

Full control via REST – no fluff:

```bash
# Generate and stream a scene
curl -X POST http://localhost:8000/api/v1/timepoints/generate/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "signing of the declaration of independence", "generate_image": true}'

# Interrogate a player
curl -X POST http://localhost:8000/api/v1/interactions/{id}/chat \
  -H "Content-Type: application/json" \
  -d '{"character": "Benjamin Franklin", "message": "What do you think of this document?"}'
```

Swagger docs live at `http://localhost:8000/docs`.

Deep dive: [docs/API.md](docs/API.md)

---

## Configure Your Rig

Snag a free key from [Google AI Studio](https://aistudio.google.com) or [OpenRouter](https://openrouter.ai).

```bash
# .env
GOOGLE_API_KEY=your-key        # Core thrust (or OPENROUTER_API_KEY for alternatives)
DATABASE_URL=sqlite+aiosqlite:///./timepoint.db  # Plug-and-play storage
```

Preset dials:

| Preset | Cycle Time | Provider | Lock For |
|--------|------------|----------|----------|
| **Hyper** | ~50s | OpenRouter | Quick scans, prototyping |
| **Balanced** | ~90s | Google Native | Solid builds |
| **HD** | ~2 min | Google Native | Max fidelity (extended thinking) |
| **Gemini3** | ~45s | OpenRouter | Latest thinking model, agentic workflows |

Image generation never fails – 3-tier fallback:

| Priority | Provider | Status |
|----------|----------|--------|
| 1 | Google Imagen | Highest quality |
| 2 | OpenRouter Flux | Fast alternative |
| 3 | Pollinations.ai | Free, always works |

---

## Testing

Run the comprehensive test suite:

```bash
./tests/test-demo.sh          # Standard mode (57 tests)
./tests/test-demo.sh --quick  # Fast validation only
./tests/test-demo.sh --bulk   # Full generation tests for all presets
```

Test suite v2.3.0 covers:
- Health and model endpoints
- All quality presets (HD, Balanced, Hyper, Gemini3)
- Generation (sync/streaming)
- Character interactions (chat, dialog, survey)
- Temporal navigation
- Image generation with 3-tier fallback (Google → OpenRouter → Pollinations.ai)
- Historical grounding and accuracy verification

---

## Dive Deeper

- [API Reference](docs/API.md) – Endpoint blueprints.
- [Temporal Shifts](docs/TEMPORAL.md) – Navigate the continuum.
- [Agent Architecture](docs/AGENTS.md) – Pipeline breakdown.

Join the lab: Contribute mods, fork for your stack, or reach out [@seanmcdonaldxyz](https://x.com/seanmcdonaldxyz) for enterprise support and hosted inference.

---

## License

Apache 2.0

---

**Wired with** Python, FastAPI, Google Gemini – Part of Timepoint AI's synthetic time travel ecosystem.
