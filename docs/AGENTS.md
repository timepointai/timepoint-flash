# How TIMEPOINT Flash Works

TIMEPOINT generates scenes using 15 specialized AI agents that each handle one part of the process
in parallel.

## The Pipeline

```
Your Query: "signing of the declaration of independence"
                           ↓
┌──────────────────────────────────────────────────────────┐
│  Judge → Timeline → Scene ──┬── Characters ── Graph      │
│                             │        ↓                   │
│                             ├── Moment                   │
│                             │        ↓                   │
│                             └── Dialog → Camera          │
│                                          ↓               │
│                                   ImagePrompt → Image    │
└──────────────────────────────────────────────────────────┘
                           ↓
    Complete scene with 8 characters, dialog, relationships, image
```

**Why 15 agents instead of one big prompt?**

1. **Speed** - Independent agents run in parallel, cutting time by ~40%
2. **Quality** - Each agent has a focused prompt optimized for one task
3. **Reliability** - If image generation fails, you still get the scene
4. **Visibility** - You see progress as each step completes

## What Each Agent Does

| Agent | Job | Output |
|-------|-----|--------|
| **Judge** | Is this a valid historical query? | yes/no, confidence |
| **Timeline** | When exactly? | year, month, day, time of day |
| **Scene** | Where and what's the atmosphere? | location, weather, mood |
| **Characters** | Who's there? | 8 people with names, roles, bios |
| **Graph** | How do they relate? | alliances, tensions, history |
| **Moment** | What's the dramatic tension? | stakes, conflict, emotion |
| **Dialog** | What are they saying? | 7 period-appropriate lines |
| **Camera** | How should we frame this? | composition, focal point |
| **ImagePrompt** | Describe the image in detail | ~11,000 character prompt |
| **ImageGen** | Create the image | photorealistic scene |

Plus 3 more for interactions: **Chat** (talk to characters), **Dialog Extension** (more lines), **Survey** (ask everyone the same question).

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
├── judge.py           # Query validation
├── timeline.py        # Date extraction
├── scene.py           # Environment
├── characters.py      # Character generation
├── graph.py           # Relationships
├── moment.py          # Dramatic tension
├── dialog.py          # Period dialog
├── camera.py          # Visual composition
├── image_prompt.py    # Prompt assembly
├── image_gen.py       # Image generation
├── character_chat.py  # Chat interactions
├── dialog_extension.py
└── survey.py
```
