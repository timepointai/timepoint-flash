# How TIMEPOINT Flash Works

TIMEPOINT generates scenes using 14 specialized AI agents that each handle one part of the process,
with parallelism where possible.

## The Pipeline

```
Your Query: "signing of the declaration of independence"
                           ↓
┌──────────────────────────────────────────────────────────────────────┐
│  Judge → Timeline → Grounding → Scene ──┬── Characters ─ Graph      │
│              ↓                          │        ↓                   │
│    (Google Search                       ├── Moment                   │
│     verification)                       │        ↓                   │
│                                         └── Dialog → Camera          │
│                                                      ↓               │
│                                               ImagePrompt            │
│                                                      ↓               │
│                                            ImagePromptOptimizer      │
│                                                      ↓               │
│                                                   ImageGen           │
└──────────────────────────────────────────────────────────────────────┘
                           ↓
    Complete scene with up to 8 characters, dialog, relationships, grounded facts, image
```

**Why multiple agents instead of one big prompt?**

1. **Speed** - Independent agents run in parallel, cutting time by ~40%
2. **Quality** - Each agent has a focused prompt optimized for one task
3. **Accuracy** - Grounding agent verifies facts via Google Search before generation
4. **Reliability** - If image generation fails, you still get the scene
5. **Visibility** - You see progress as each step completes

## What Each Agent Does

| Agent | Job | Output |
|-------|-----|--------|
| **Judge** | Is this a valid historical query? | yes/no, confidence, detected figures |
| **Timeline** | When exactly? | year, month, day, time of day |
| **Grounding** | Verify facts via Google Search | verified location, date, participants, physical presence |
| **Scene** | Where and what's the atmosphere? | location, weather, mood |
| **Characters** | Who's there? | 8 people with names, roles, bios |
| **Graph** | How do they relate? | alliances, tensions, history |
| **Moment** | What's the dramatic tension? | stakes, conflict, emotion |
| **Dialog** | What are they saying? | 7 period-appropriate lines |
| **Camera** | How should we frame this? | composition, focal point |
| **ImagePrompt** | Describe the image in detail | ~5,000-11,000 character prompt with grounded facts |
| **ImagePromptOptimizer** | Compress prompt for image gen limits | Shortened prompt preserving key visual details |
| **ImageGen** | Create the image | photorealistic scene (3-tier fallback: Google → OpenRouter → Pollinations.ai) |

Plus 3 more for interactions: **Chat** (talk to characters), **Dialog Extension** (more lines), **Survey** (ask everyone the same question).

Note: The Characters step internally uses 3 sub-agents: **CharacterIdentification** (detect who's present), **Graph** (extract relationships), and **CharacterBio** (generate detailed bios for each character).

## The Grounding Agent (Technical Details)

The Grounding agent uses Google Search to verify historical facts before generation. This prevents hallucinations like putting Kasparov in "an IBM server room" when the match was actually held in a theater.

**When Grounding is Triggered:**
- Query type is HISTORICAL (not fictional/hypothetical)
- Judge detected specific historical figures (not generic scenes)

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

## Parallel Execution

The pipeline doesn't wait for each step:

```
Phase 1 (sequential): Judge → Timeline → Scene
Phase 2 (parallel):   Characters + Moment + Camera (all at once)
Phase 3 (sequential): Dialog → ImagePrompt → ImageGen
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
├── image_prompt_optimizer.py # Compress prompt for image gen limits
├── image_gen.py              # Image generation (3-tier fallback)
├── character_chat.py         # Chat interactions
├── dialog_extension.py       # Extended dialog generation
└── survey.py                 # Multi-character survey
```

---

*Last updated: 2026-02-05*
