# How TIMEPOINT Flash Works

TIMEPOINT generates scenes using 14 specialized AI agents that each handle one part of the process,
with parallelism where possible.

## The Pipeline

```
Your Query: "Oppenheimer watches the Trinity test, 5:29 AM July 16 1945"
                           ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Judge → Timeline → Grounding → Scene ──┬── Characters ─ Graph      │
│              ↓                          │        ↓                   │
│    (Google Search                       ├── Moment                   │
│     verification)                       │        ↓                   │
│                                         └── Dialog → Critique        │
│                                                (retry if critical)    │
│                                                      ↓               │
│                                               Camera → ImagePrompt   │
│                                                      ↓               │
│                                            ImagePromptOptimizer      │
│                                             (emotion → physicality)   │
│                                                      ↓               │
│                                                   ImageGen           │
└──────────────────────────────────────────────────────────────────────┘
                           ↓
    Complete scene with up to 6 characters, dialog, relationships, grounded facts, image
```

**Why multiple agents instead of one big prompt?**

1. **Speed** - Independent agents run in parallel, cutting time by ~40%
2. **Quality** - Each agent has a focused prompt optimized for one task
3. **Accuracy** - Grounding agent verifies facts via Google Search before generation
4. **Self-correction** - Critique agent reviews dialog for anachronisms and cultural errors, retries if critical issues found
5. **Reliability** - If image generation fails, you still get the scene
6. **Visibility** - You see progress as each step completes

## What Each Agent Does

| Agent | Job | Output |
|-------|-----|--------|
| **Judge** | Is this a valid historical query? | yes/no, confidence, detected figures |
| **Timeline** | When exactly? | year, month, day, time of day |
| **Grounding** | Verify facts via Google Search | verified location, date, participants, physical presence |
| **Scene** | Where and what's the atmosphere? | location, weather, mood |
| **Characters** | Who's there? | Up to 6 people with names, roles, bios, social registers |
| **Graph** | How do they relate? | alliances, tensions, history (pruned to significant pairs only) |
| **Moment** | What's the dramatic tension? | stakes, conflict, emotion |
| **Dialog** | What are they saying? | Up to 7 voice-differentiated lines |
| **Critique** | Any anachronisms or errors? | Issues list; retriggers dialog if critical |
| **Camera** | How should we frame this? | composition, focal point |
| **ImagePrompt** | Describe the image in detail | ~5,000-11,000 character prompt with grounded facts |
| **ImagePromptOptimizer** | Compress + physicalize emotion | ~77 words with tension translated to body language |
| **ImageGen** | Create the image | photorealistic scene (3-tier fallback: Google → OpenRouter → Pollinations.ai) |

Plus 3 more for interactions: **Chat** (talk to characters), **Dialog Extension** (more lines), **Survey** (ask everyone the same question). All interaction endpoints check timepoint visibility — private timepoints block non-owner access (403). When `AUTH_ENABLED=true`, interactions also require a Bearer JWT and deduct credits.

Note: The Characters step internally uses 3 sub-agents: **CharacterIdentification** (detect who's present, with grounding data for name authenticity), **Graph** (extract significant relationships, pruned to 2x character count), and **CharacterBio** (generate detailed bios with social register and voice differentiation).

## The Grounding Agent (Technical Details)

The Grounding agent uses Google Search to verify historical facts before generation. This prevents hallucinations like putting Kasparov in "an IBM server room" when the match was actually held in a theater.

**When Grounding is Triggered:**
- Query type is HISTORICAL (not fictional/hypothetical)
- The grounding agent itself discovers participants via Google Search — no pre-detection by Judge required

**What Gets Verified:**
```python
class GroundedContext:
    # Location verification
    verified_location: str       # "Equitable Center, 35th floor, Manhattan"
    venue_description: str       # "Theater-style room with raised seating"

    # Date verification
    verified_date: str           # "May 11, 1997"
    verified_year: int           # 1997

    # Participant verification
    verified_participants: list[str]  # ["Garry Kasparov", "Feng-hsiung Hsu", ...]

    # Physical presence (critical for image generation)
    physical_participants: list[str]  # ["Kasparov sitting at chess board", "IBM operator across from him"]
    entity_representations: list[str] # ["Deep Blue: IBM operator relaying moves"]

    # Event mechanics
    event_mechanics: str         # How the event physically worked
    visible_technology: str      # Period-accurate equipment descriptions
    photographic_reality: str    # What a photograph would actually show

    # Context
    historical_context: str      # Significance of the event
    source_citations: list[str]  # URLs from Google Search
    grounding_confidence: float  # 0.0-1.0
```

**Why Physical Presence Matters:**

Non-human entities (computers, AI, organizations) can't appear in images. The grounding agent discovers WHO represented them:

| Entity | Physical Representation |
|--------|------------------------|
| Deep Blue | IBM operator sitting across from Kasparov |
| "The Government" | The official who signed the document |
| HAL 9000 | Red camera lens on the wall |

This ensures images show *people* where people were present, not empty chairs or abstract representations.

## The Graph Agent (Technical Details)

The Graph agent extracts a structured relationship network from the characters. No graph library is used—it's pure LLM extraction into a graph-ready schema.

**Schema:**

```python
# Directed edges with attributes
class Relationship:
    from_character: str      # "Brutus"
    to_character: str        # "Caesar"
    relationship_type: str   # ally|rival|enemy|subordinate|leader|mentor|family|friend|stranger|neutral
    tension_level: str       # friendly|neutral|tense|hostile
    description: str         # "Surrogate father/son, now betrayer"

# Faction clustering
class Faction:
    name: str               # "Conspirators"
    members: list[str]      # ["Brutus", "Cassius", "Casca"]
    goal: str               # "End tyranny, restore the Republic"

# Full graph output
class GraphData:
    relationships: list[Relationship]
    factions: list[Faction]
    power_dynamics: str     # "Caesar holds absolute power..."
    central_conflict: str   # "Loyalty vs. duty to Rome"
    alliances: list[str]    # Key alliance descriptions
    rivalries: list[str]    # Key rivalry descriptions
    historical_context: str # Background for relationships
```

**Example output (Caesar assassination):**

```json
{
  "relationships": [
    {"from": "Brutus", "to": "Caesar", "type": "family", "tension": "hostile"},
    {"from": "Cassius", "to": "Brutus", "type": "ally", "tension": "tense"},
    {"from": "Antony", "to": "Caesar", "type": "ally", "tension": "friendly"}
  ],
  "factions": [
    {"name": "Conspirators", "members": ["Brutus", "Cassius", "Casca"], "goal": "End tyranny"},
    {"name": "Loyalists", "members": ["Antony", "Lepidus"], "goal": "Protect Caesar"}
  ],
  "power_dynamics": "Caesar holds dictatorial power; Senate is divided",
  "central_conflict": "Republic vs. autocracy, loyalty vs. principle"
}
```

**Graph-ready:** The `Relationship.to_edge()` method returns `(from, to, type)` tuples for easy conversion to networkx/igraph if you want to add visualization.

## Example Output: AlphaGo Move 37

Query: `"AlphaGo plays Move 37 against Lee Sedol in Game 2, the move no human would make, Four Seasons Hotel Seoul March 10 2016"`

**What the pipeline produced:**

```
Location:  Four Seasons Hotel, Seoul, South Korea
Date:      2016-03-10, afternoon, spring
Tension:   high
Image:     generated (gemini-2.5-flash-image)
```

**Scene:** A brightly lit conference room arranged for a Go tournament. Central Go board on a low, polished wooden table. Lee Sedol sits opposite the AlphaGo system, represented by a monitor. Journalists, AI researchers, and Go enthusiasts seated behind a low barrier. Cables connecting the AlphaGo system to power and network.

**Characters (5 speaking + 3 background):**

| Character | Role | Voice |
|-----------|------|-------|
| Lee Sedol | primary | Short, halting fragments — stunned understatement |
| Commentator 1 | secondary | Chatty, analytical, comfortable on-air cadence |
| Commentator 2 | secondary | More measured, technical |
| Tournament Official | secondary | Formal, procedural |
| AlphaGo | primary (silent) | Represented by monitor — grounding agent correctly identified non-human entity |

**Dialog excerpt:**

> **Lee Sedol:** "...Huh. That's... certainly a move."
>
> **Commentator 1:** "I'm not sure I've ever seen a professional play quite like that before."
>
> **Lee Sedol:** "It's... unexpected, to say the least."
>
> **Commentator 1:** "It's either genius or madness, and I honestly can't tell which right now."

**What this demonstrates:**
- **Grounding agent** correctly resolved AlphaGo as a non-human entity represented by a monitor
- **Voice differentiation** — Lee Sedol's halting fragments vs. commentator's fluid analysis
- **Emotional transfer** — image optimizer translated "high tension" into physical cues (Sedol's posture, focused expressions)
- **Scene accuracy** — Four Seasons Hotel setup matches documented tournament configuration

---

## Narrative Arc System (Dialog)

The dialog agent uses a **narrative arc** to constrain 7 lines into a coherent micro-story. This forces dialog complexity to O(n) instead of O(2^n) — more characters don't mean more incoherent cross-talk. Every scene follows exposition → complication → climax → resolution, regardless of cast size.

**Six Vonnegut shapes + Freytag's pyramid:**

| Shape | Pattern | Example |
|-------|---------|---------|
| Man in Hole | Good → Bad → Good | Rescue mission, comeback |
| Creation | Low → Steady Rise | Apollo 11, Woodstock |
| Cinderella | Low → High → Low → Very High | Rags to riches |
| From Bad to Worse | Bad → Worse | Pompeii, Titanic |
| Old Testament | Rise → Deep Fall | Icarus, Sarajevo |
| Freytag | Exposition → Climax → Denouement | Standard dramatic pyramid |

**How it works:**

1. MomentData's `tension_arc` maps to a narrative shape (climactic → Freytag, rising → Creation, etc.)
2. Each shape defines 7 beats with narrative functions: `establish`, `complicate`, `escalate`, `turn`, `react`, `resolve`, `punctuate`
3. Each beat has an emotional target, intensity curve, and speaker role preference
4. The dialog agent selects speakers based on beat roles (TURN → focal character, REACT → different character, PUNCTUATE → background/outsider)
5. Beat context is injected into each line's prompt: "Your line should {turn} the scene. Target emotion: {revelation}. Intensity: high."

**Speaker selection logic:**
- TURN/ESCALATE beats → primary/focal character
- REACT beats → different character than previous speaker
- PUNCTUATE beats → background character (outsider perspective)
- Always avoids repeating the last speaker when possible
- Falls back to rotation pattern when no arc is available

**Schema:** `app/schemas/dialog_arc.py` — `DialogArc`, `ArcBeat`, `NarrativeShape`, `NarrativeFunction`, `build_arc_from_moment()`

---

## Parallel Execution

The pipeline doesn't wait for each step:

```
Phase 1 (sequential): Judge → Timeline → Grounding → Scene
Phase 2 (parallel):   Characters (with grounding) + Moment + Camera (all at once)
Phase 3 (sequential): Dialog → Critique (retry if needed) → ImagePrompt → Optimize → ImageGen
```

## Adding Your Own Agent

1. Create schema: `app/schemas/your_agent.py`
2. Create prompt: `app/prompts/your_agent.py`
3. Create agent: `app/agents/your_agent.py`
4. Wire into pipeline: `app/core/pipeline.py`
5. Add tests: `tests/unit/test_your_agent.py`

All agents follow the same pattern:

```python
class YourAgent:
    async def run(self, input: InputSchema) -> OutputSchema:
        prompt = self._build_prompt(input)
        return await self.router.call(prompt=prompt, response_model=OutputSchema)
```

## Code Location

```
app/agents/
├── judge.py                  # Query validation
├── timeline.py               # Date extraction
├── grounding.py              # Google Search fact verification
├── scene.py                  # Environment
├── character_identification.py  # Detect who's present
├── character_bio.py          # Generate detailed character bios
├── characters.py             # Character generation (orchestrator)
├── graph.py                  # Relationships
├── moment.py                 # Dramatic tension
├── dialog.py                 # Period dialog
├── camera.py                 # Visual composition
├── image_prompt.py           # Prompt assembly (with grounded facts)
├── image_prompt_optimizer.py # Compress prompt + physicalize emotion (~77 words)
├── image_gen.py              # Image generation (3-tier fallback)
├── critique.py               # Post-generation quality review (anachronisms, voice, cultural errors)
├── character_chat.py         # Chat interactions
├── dialog_extension.py       # Extended dialog generation
└── survey.py                 # Multi-character survey
```

---

*Last updated: 2026-02-16*
