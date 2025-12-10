# TIMEPOINT Flash Agent Architecture

TIMEPOINT Flash uses a multi-agent pipeline where 15 specialized AI agents collaborate to generate immersive historical scenes.

---

## How It Works

```
Query: "signing of the declaration of independence"
                    |
                    v
    ┌─────────────────────────────────────────────────────────────┐
    │                    GENERATION PIPELINE                       │
    │                                                              │
    │  Judge -> Timeline -> Scene -> Characters -> Moment          │
    │                                    |                         │
    │  ImageGen <- ImagePrompt <- Graph <- Camera <- Dialog        │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
                    |
                    v
    Scene + 8 Characters + Dialog + Relationships + Image
```

Each agent is a specialist: one validates queries, one extracts dates, one creates characters, one writes dialog, etc. They pass structured data to each other, building up a complete scene.

---

## The 15 Agents

### Generation Pipeline (10 agents)

| # | Agent | Purpose | Output |
|---|-------|---------|--------|
| 1 | **JudgeAgent** | Validates query, classifies type | `is_valid`, `query_type`, `confidence` |
| 2 | **TimelineAgent** | Extracts temporal coordinates | `year`, `month`, `day`, `season`, `time_of_day` |
| 3 | **SceneAgent** | Creates environment & atmosphere | Location, weather, lighting, sounds |
| 4 | **CharactersAgent** | Generates up to 8 characters | Names, roles, appearances, bios |
| 5 | **MomentAgent** | Defines plot, tension, stakes | What's happening, why it matters |
| 6 | **DialogAgent** | Writes period-appropriate dialog | 7 lines of authentic speech |
| 7 | **CameraAgent** | Composes the visual frame | Shot type, focal point, depth |
| 8 | **GraphAgent** | Maps character relationships | Who knows whom, alliances, tensions |
| 9 | **ImagePromptAgent** | Assembles the image prompt | 11K character detailed description |
| 10 | **ImageGenAgent** | Generates the final image | Photorealistic scene image |

### Character Interactions (3 agents)

| # | Agent | Purpose | Output |
|---|-------|---------|--------|
| 11 | **CharacterChatAgent** | Conversations with characters | In-character responses |
| 12 | **DialogExtensionAgent** | Extends scene dialog | Additional lines |
| 13 | **SurveyAgent** | Surveys multiple characters | Responses with sentiment |

### Character Bio Generation (2 agents)

| # | Agent | Purpose | Output |
|---|-------|---------|--------|
| 14 | **CharacterIdentificationAgent** | Fast character identification | Names, roles (lightweight) |
| 15 | **CharacterBioAgent** | Detailed character bios | Full bio with graph context |

---

## Parallel Execution

The pipeline doesn't run sequentially. Independent agents run in parallel:

```
Phase 1 (sequential): Judge -> Timeline -> Scene
Phase 2 (parallel):   Characters (ID -> Graph -> Bios in parallel)
                      + Camera (starts after Scene)
                      + Moment
Phase 3 (sequential): Dialog -> ImagePrompt -> ImageGen
```

This reduces total latency by ~40% compared to pure sequential execution.

---

## Model Tiers & Parallelism

Different model tiers get different parallelism levels to avoid rate limits:

| Tier | Models | Max Parallel Calls |
|------|--------|-------------------|
| FREE | `:free` suffix models | 1 (sequential) |
| PAID | OpenRouter paid models | 2-3 |
| NATIVE | Google Gemini direct | 3-5 |

---

## Agent Code Location

All agents live in `app/agents/`:

```
app/agents/
├── judge.py              # Query validation
├── timeline.py           # Temporal extraction
├── scene.py              # Environment generation
├── characters.py         # Character generation (single-call fallback)
├── character_identification.py  # Fast ID phase
├── character_bio.py      # Detailed bio phase
├── moment.py             # Plot/tension/stakes
├── dialog.py             # Period dialog
├── camera.py             # Visual composition
├── graph.py              # Relationship mapping
├── image_prompt.py       # Prompt assembly
├── image_gen.py          # Image generation
├── character_chat.py     # Chat interactions
├── dialog_extension.py   # Dialog extension
└── survey.py             # Character surveys
```

---

## Agent Interface

All agents follow a consistent pattern:

```python
class ExampleAgent:
    def __init__(self, router: LLMRouter):
        self.router = router

    async def run(self, input: InputSchema) -> OutputSchema:
        prompt = self._build_prompt(input)
        response = await self.router.call(
            prompt=prompt,
            response_model=OutputSchema,
            temperature=0.7
        )
        return response
```

Key points:
- Agents receive an `LLMRouter` for model abstraction
- Input/output are Pydantic schemas for type safety
- Prompts are built from templates in `app/prompts/`
- Response models enable structured JSON output

---

## Adding a New Agent

1. Create schema in `app/schemas/your_agent.py`
2. Create prompt in `app/prompts/your_agent.py`
3. Create agent in `app/agents/your_agent.py`
4. Add to pipeline in `app/core/pipeline.py`
5. Add tests in `tests/unit/test_your_agent.py`

---

## Why Multi-Agent?

| Approach | Pros | Cons |
|----------|------|------|
| **Single mega-prompt** | Simpler, one call | Less control, harder to debug |
| **Multi-agent pipeline** | Specialized prompts, parallel execution, step-by-step progress | More complexity, more calls |

TIMEPOINT Flash uses multi-agent because:
1. **Specialization** - Each agent has a focused prompt optimized for one task
2. **Parallelism** - Independent agents run concurrently
3. **Transparency** - SSE events show progress through each step
4. **Reliability** - One step failing doesn't crash the whole pipeline
5. **Flexibility** - Easy to swap models per agent or add new agents

---

## Learn More

- [API Reference](API.md) - All endpoints including agent outputs
- [Temporal Navigation](TEMPORAL.md) - Time travel between moments
