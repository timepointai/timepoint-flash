# TIMEPOINT Flash v2.0 - Complete Refactor Plan

**Status**: Planning Phase
**Date**: 2025-11-26
**Goal**: Clean, production-ready multi-agent temporal simulation system

---

## Executive Summary

Complete architectural rebuild focused on:
1. **Clean provider abstraction** - Google AI (pro mode) + OpenRouter (multi-model)
2. **Mirascope-powered model management** - unified LLM interface
3. **Synthetic time system** - interoperable temporal navigation
4. **Batteries-included UX** - `tp "signing of the declaration"` → full render
5. **Production-grade FastAPI** - tight server with OpenAPI, HTMX viewer
6. **Test-driven development** - pytest with docstrings, stubs, labels

---

## 1. Research Findings

### Google Gemini API (2025)

**Available Models:**
- `gemini-3-pro-preview` - flagship model for complex reasoning (NEW)
- `gemini-2.5-flash` - fast logic/judging (NO gemini-3-flash exists)
- `gemini-2.5-pro` - creative generation
- `imagen-3.0-generate-002` - Imagen 3 via direct API ($0.03/image)
- Nano Banana Pro (`gemini-3-pro-image`) via OpenRouter ($0.00012/image)

**SDK:** `google.genai` (Gen AI SDK for Python v1.51.0+)

**Key Features:**
- `thinking_level` parameter for reasoning depth
- Automatic Thought Signatures
- Function calling, Google Search, Code Execution

### OpenRouter API (2025)

**Dynamic Discovery:** `GET https://openrouter.ai/api/v1/models`

**Response:**
```json
{
  "data": [
    {
      "id": "anthropic/claude-3.5-sonnet",
      "name": "Anthropic: Claude 3.5 Sonnet",
      "context_length": 200000,
      "pricing": {"prompt": "0.000003", "completion": "0.000015"},
      "architecture": {"modality": "text+image->text"}
    }
  ]
}
```

**Capabilities:**
- 300+ models (proprietary + open source)
- Real-time pricing, context length, capability metadata
- Unified chat/completions endpoint

### Mirascope (2025)

**Version:** 1.25.6+ (stable), 2.0.0a0 (preview)

**Core API:**
```python
from mirascope import llm

@llm.call(provider="google", model="gemini-3-pro-preview")
def generate_scene(prompt: str) -> SceneContext:
    """Generate historical scene context."""
    return f"Create scene: {prompt}"
```

**Providers:** OpenAI, Anthropic, Google (Gemini/Vertex), Groq, Cohere, LiteLLM, Azure, Bedrock

**Features:**
- Native Pydantic `response_model` (structured outputs)
- Function chaining (perfect for LangGraph)
- No abstraction overhead (unlike LangChain)

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI Entry Point                        │
│              tp "signing of the declaration"                 │
└─────────────────────────────────┬───────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │   LLM Router (Mirascope)  │
                    │  - Google AI (Pro Mode)   │
                    │  - OpenRouter (Multi)     │
                    │  - Auto model selection   │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │                         │                         │
┌───────▼────────┐    ┌──────────▼─────────┐    ┌─────────▼────────┐
│ Judge Agent    │    │  Timeline Agent    │    │  Scene Agent     │
│ (validate)     │───▶│  (year/season/loc) │───▶│  (environment)   │
└────────────────┘    └────────────────────┘    └──────────────────┘
                                                          │
                      ┌───────────────────────────────────┤
                      │                                   │
            ┌─────────▼─────────┐            ┌───────────▼──────────┐
            │  Characters Agent │            │   Moment Agent       │
            │  (8 characters)   │◀───────────│   (plot/tension)     │
            └─────────┬─────────┘            └──────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        │                           │
┌───────▼────────┐      ┌──────────▼─────────┐
│  Dialog Agent  │      │  Camera Agent      │
│  (7 lines)     │      │  (composition)     │
└───────┬────────┘      └──────────┬─────────┘
        │                          │
        └──────────┬───────────────┘
                   │
        ┌──────────▼─────────┐
        │  Scene Graph Agent │
        │  (relationships)   │
        └──────────┬─────────┘
                   │
        ┌──────────▼─────────┐
        │ Image Prompt Agent │
        │ (11k char prompt)  │
        └──────────┬─────────┘
                   │
        ┌──────────▼─────────┐
        │  Image Gen Agent   │
        │  (Nano Banana Pro) │
        └──────────┬─────────┘
                   │
        ┌──────────▼─────────┐
        │ Segmentation Agent │
        │ (character masks)  │
        └────────────────────┘
```

---

## 3. Core Components

### 3.1 Provider Abstraction Layer

**New file:** `app/core/providers.py`

```python
from abc import ABC, abstractmethod
from enum import Enum
from pydantic import BaseModel

class ProviderType(str, Enum):
    GOOGLE = "google"
    OPENROUTER = "openrouter"

class ModelCapability(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VISION = "vision"

class ProviderConfig(BaseModel):
    """Provider configuration with fallback chain."""
    primary: ProviderType
    fallback: ProviderType | None
    capabilities: dict[ModelCapability, str]  # capability -> model_id

class LLMProvider(ABC):
    """Base provider interface."""

    @abstractmethod
    async def call_text(self, prompt: str, model: str, response_model: Type[T]) -> T:
        """Generate text with structured output."""
        pass

    @abstractmethod
    async def generate_image(self, prompt: str, model: str) -> str:
        """Generate image, return base64."""
        pass

    @abstractmethod
    async def analyze_image(self, image: str, prompt: str, model: str) -> dict:
        """Vision analysis."""
        pass
```

**Implementations:**
- `app/core/providers/google.py` - Google Gen AI SDK integration
- `app/core/providers/openrouter.py` - OpenRouter API integration

### 3.2 LLM Router (Mirascope Integration)

**New file:** `app/core/llm_router.py`

```python
from mirascope import llm
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class LLMRouter:
    """Route LLM calls with provider selection and fallback."""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.google = GoogleProvider()
        self.openrouter = OpenRouterProvider()

    @llm.call(provider="google", model="{self.config.capabilities[TEXT]}")
    async def call_structured(
        self,
        prompt: str,
        response_model: Type[T],
        capability: ModelCapability = ModelCapability.TEXT
    ) -> T:
        """Call LLM with automatic provider selection and fallback."""
        try:
            # Primary provider
            provider = self._get_provider(self.config.primary)
            model = self.config.capabilities[capability]
            return await provider.call_text(prompt, model, response_model)
        except Exception as e:
            # Fallback provider
            if self.config.fallback:
                logger.warning(f"Primary failed, using fallback: {e}")
                provider = self._get_provider(self.config.fallback)
                return await provider.call_text(prompt, model, response_model)
            raise
```

### 3.3 Synthetic Time System

**New file:** `app/core/temporal.py`

```python
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum

class TimeUnit(str, Enum):
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

class TemporalPoint(BaseModel):
    """Interoperable temporal coordinate."""
    year: int
    month: int | None = None
    day: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None

    # Metadata
    season: str | None = None
    time_of_day: str | None = None
    era: str | None = None

    def to_datetime(self) -> datetime:
        """Convert to Python datetime (best effort)."""
        return datetime(
            self.year,
            self.month or 1,
            self.day or 1,
            self.hour or 0,
            self.minute or 0,
            self.second or 0
        )

    def step(self, units: int, unit: TimeUnit) -> "TemporalPoint":
        """Step forward/backward in time."""
        dt = self.to_datetime()

        delta_map = {
            TimeUnit.SECOND: timedelta(seconds=units),
            TimeUnit.MINUTE: timedelta(minutes=units),
            TimeUnit.HOUR: timedelta(hours=units),
            TimeUnit.DAY: timedelta(days=units),
            TimeUnit.WEEK: timedelta(weeks=units),
            TimeUnit.MONTH: timedelta(days=units * 30),  # Approximate
            TimeUnit.YEAR: timedelta(days=units * 365),  # Approximate
        }

        new_dt = dt + delta_map[unit]
        return TemporalPoint.from_datetime(new_dt)

    @classmethod
    def from_datetime(cls, dt: datetime) -> "TemporalPoint":
        """Create from Python datetime."""
        return cls(
            year=dt.year,
            month=dt.month,
            day=dt.day,
            hour=dt.hour,
            minute=dt.minute,
            second=dt.second
        )

class TemporalNavigator:
    """Navigate through temporal points."""

    async def next_moment(
        self,
        current: Timepoint,
        units: int = 1,
        unit: TimeUnit = TimeUnit.DAY
    ) -> Timepoint:
        """Generate next temporal moment from current timepoint."""
        # Step temporal coordinate
        next_temporal = current.temporal_point.step(units, unit)

        # Build context prompt
        prompt = f"""Here is timepoint data from {current.temporal_point}:

Characters: {current.character_data_json}
Scene: {current.metadata_json['scene']}
Location: {current.metadata_json['timeline']['location']}

Generate the scene for {units} {unit} forward at {next_temporal}.
Same characters, same location, natural progression of events."""

        # Run workflow with context
        return await self.generate_with_context(prompt, next_temporal, current)
```

### 3.4 Batch Processing

**New file:** `app/core/batch.py`

```python
import csv
from pathlib import Path
from pydantic import BaseModel

class BatchConfig(BaseModel):
    """Configuration for batch processing."""
    csv_path: Path
    output_dir: Path
    concurrent_limit: int = 3

class BatchProcessor:
    """Process CSV of timepoint requests."""

    async def process_csv(self, config: BatchConfig):
        """Process CSV file with timepoint queries."""
        with open(config.csv_path) as f:
            reader = csv.DictReader(f)
            tasks = []

            for row in reader:
                task = self.process_row(row)
                tasks.append(task)

                # Process in batches
                if len(tasks) >= config.concurrent_limit:
                    await asyncio.gather(*tasks)
                    tasks = []

            # Process remaining
            if tasks:
                await asyncio.gather(*tasks)

    async def process_row(self, row: dict):
        """Process single CSV row."""
        query = row['query']
        email = row.get('email', 'batch@timepoint.ai')

        # Generate timepoint
        result = await generate_timepoint(query, email)

        # Save to output
        self.save_result(result)
```

---

## 4. CLI Design

### 4.1 Simple Autopilot Mode

```bash
# One-command generation
tp "signing of the declaration of independence"

# With temporal navigation
tp "signing of the declaration" --next 10 --unit days

# Batch mode
tp batch timeline.csv --concurrent 5

# Model selection
tp "rome 50 BCE" --provider openrouter --model "anthropic/claude-3.5-sonnet"
```

**Implementation:** `app/cli.py`

```python
import click
from rich.console import Console

@click.group()
def cli():
    """TIMEPOINT Flash - AI-powered temporal simulation."""
    pass

@cli.command()
@click.argument('query')
@click.option('--next', type=int, help='Generate N moments forward')
@click.option('--unit', type=str, default='day', help='Time unit (day/week/month)')
@click.option('--provider', type=str, help='LLM provider (google/openrouter)')
@click.option('--model', type=str, help='Model ID')
def generate(query, next, unit, provider, model):
    """Generate timepoint from natural language query."""
    console = Console()

    with console.status(f"[bold green]Generating: {query}"):
        # Run workflow
        result = asyncio.run(run_workflow(query, provider, model))

    console.print(f"✅ Generated: {result.slug}")
    console.print(f"🖼️  View: http://localhost:8000/view/{result.slug}")

    # Temporal navigation
    if next:
        with console.status(f"[bold cyan]Generating {next} {unit} forward..."):
            results = asyncio.run(
                generate_sequence(result, next, unit)
            )
        console.print(f"✅ Generated {len(results)} timepoints")
```

### 4.2 Model Discovery CLI

```bash
# List available models from OpenRouter
tp models list

# Search models
tp models search "claude"

# Show model details
tp models info "anthropic/claude-3.5-sonnet"
```

---

## 5. Testing Strategy

### 5.1 Pytest with Docstrings & Stubs

**Philosophy:** Tight sync between code, docs, and tests

```python
# app/agents/judge.py
async def validate_query(query: str) -> ValidationResult:
    """Validate temporal query for generation.

    Args:
        query: Natural language temporal query

    Returns:
        ValidationResult with is_valid and cleaned_query

    Examples:
        >>> await validate_query("Rome 50 BCE")
        ValidationResult(is_valid=True, cleaned_query="Ancient Rome, 50 BCE")

        >>> await validate_query("xyzabc nonsense")
        ValidationResult(is_valid=False, reason="Not a temporal query")

    Tests:
        - tests/agents/test_judge.py::test_validate_historical_query
        - tests/agents/test_judge.py::test_validate_invalid_query
        - tests/agents/test_judge.py::test_validate_fictional_query
    """
    pass
```

**Test file:** `tests/agents/test_judge.py`

```python
import pytest
from app.agents.judge import validate_query

@pytest.mark.fast
@pytest.mark.unit
async def test_validate_historical_query():
    """Test validation of valid historical query (docstring example 1)."""
    result = await validate_query("Rome 50 BCE")
    assert result.is_valid
    assert "rome" in result.cleaned_query.lower()

@pytest.mark.fast
@pytest.mark.unit
async def test_validate_invalid_query():
    """Test rejection of nonsense query (docstring example 2)."""
    result = await validate_query("xyzabc nonsense")
    assert not result.is_valid
    assert result.reason

@pytest.mark.e2e
@pytest.mark.requires_api
async def test_validate_with_llm():
    """Test validation with real LLM (full integration)."""
    result = await validate_query("signing of the declaration")
    assert result.is_valid
```

### 5.2 Test Organization

```
tests/
├── conftest.py              # Fixtures, markers
├── unit/                    # Fast tests, no API
│   ├── test_temporal.py
│   ├── test_providers.py
│   └── test_models.py
├── integration/             # Component tests
│   ├── test_llm_router.py
│   ├── test_batch.py
│   └── test_temporal_nav.py
├── e2e/                     # Full workflow
│   ├── test_workflow.py
│   ├── test_temporal_sequence.py
│   └── test_cli.py
└── fixtures/
    ├── mock_responses.json
    └── test_timepoints.json
```

**Run commands:**
```bash
pytest -m fast              # Unit tests (~5s)
pytest -m integration       # Integration tests (~30s)
pytest -m e2e              # E2E tests (~10min, requires API)
pytest --cov               # With coverage
pytest -k "judge"          # Specific component
```

---

## 6. FastAPI Server

### 6.1 API Structure

```
app/
├── main.py                  # FastAPI app
├── api/
│   ├── v1/
│   │   ├── timepoints.py    # CRUD endpoints
│   │   ├── temporal.py      # Navigation endpoints
│   │   ├── batch.py         # Batch processing
│   │   └── models.py        # Model discovery
│   └── dependencies.py      # Auth, rate limiting
├── core/
│   ├── providers.py         # Provider abstraction
│   ├── llm_router.py        # Mirascope integration
│   ├── temporal.py          # Time system
│   └── batch.py             # Batch processor
├── agents/                  # LangGraph agents
│   ├── judge.py
│   ├── timeline.py
│   ├── scene.py
│   └── ...
└── web/
    ├── templates/           # HTMX templates
    └── static/              # CSS, JS
```

### 6.2 Key Endpoints

```python
# POST /api/v1/timepoints/generate
{
  "query": "signing of the declaration",
  "provider": "google",  # optional
  "model": "gemini-3-pro-preview"  # optional
}

# POST /api/v1/timepoints/{id}/next
{
  "units": 10,
  "unit": "days"
}

# POST /api/v1/timepoints/{id}/prior
{
  "units": 1,
  "unit": "hour"
}

# GET /api/v1/models/available
# Returns OpenRouter model list

# POST /api/v1/batch/csv
# multipart/form-data with CSV file
```

### 6.3 HTMX Viewer

**Template:** `app/web/templates/viewer.html`

```html
<div hx-get="/api/v1/timepoints/{{ id }}/status"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <div class="progress">Generating...</div>
</div>

<div class="temporal-nav">
  <button hx-post="/api/v1/timepoints/{{ id }}/prior?units=1&unit=day"
          hx-target="#timepoint-container">
    ← Previous Day
  </button>

  <button hx-post="/api/v1/timepoints/{{ id }}/next?units=1&unit=day"
          hx-target="#timepoint-container">
    Next Day →
  </button>
</div>
```

---

## 7. Configuration System

**File:** `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with provider configs."""

    # Database
    DATABASE_URL: str  # sqlite:// or postgresql://

    # Provider API Keys
    GOOGLE_API_KEY: str | None = None
    OPENROUTER_API_KEY: str | None = None

    # Provider Selection
    PRIMARY_PROVIDER: ProviderType = ProviderType.GOOGLE
    FALLBACK_PROVIDER: ProviderType = ProviderType.OPENROUTER

    # Model Assignments
    JUDGE_MODEL: str = "gemini-2.5-flash"
    CREATIVE_MODEL: str = "gemini-3-pro-preview"
    IMAGE_MODEL: str = "google/gemini-3-pro-image-preview"

    # Observability
    LOGFIRE_TOKEN: str | None = None

    # Auto-detect provider based on keys
    @property
    def detected_provider(self) -> ProviderType:
        if self.GOOGLE_API_KEY:
            return ProviderType.GOOGLE
        elif self.OPENROUTER_API_KEY:
            return ProviderType.OPENROUTER
        raise ValueError("No API keys configured")

settings = Settings()
```

---

## 8. Migration Plan

### Phase 1: GitHub Cleanup (Week 1)

**Archive current codebase:**
```bash
# Create archive branch
git checkout -b archive/v1-legacy
git push origin archive/v1-legacy

# Tag current state
git tag v1.0.0-legacy
git push origin v1.0.0-legacy

# Create clean main
git checkout --orphan main-v2
git rm -rf .
git commit --allow-empty -m "chore: clean slate for v2.0 refactor"
git push -f origin main-v2:main
```

**Move old docs to archive:**
```bash
mkdir archive/
mv README.md archive/README-v1.md
mv QUICKSTART.md archive/QUICKSTART-v1.md
mv TESTING.md archive/TESTING-v1.md
```

### Phase 2: Core Infrastructure (Week 2)

1. **Setup project structure**
   - FastAPI skeleton
   - Pydantic models
   - Database (SQLite + PostgreSQL support)
   - pytest configuration

2. **Provider abstraction layer**
   - `app/core/providers.py` (base classes)
   - `app/core/providers/google.py`
   - `app/core/providers/openrouter.py`
   - Tests: `tests/unit/test_providers.py`

3. **LLM Router with Mirascope**
   - `app/core/llm_router.py`
   - Provider selection logic
   - Fallback handling
   - Tests: `tests/integration/test_llm_router.py`

### Phase 3: Temporal System (Week 3)

1. **Synthetic time implementation**
   - `app/core/temporal.py`
   - TemporalPoint class
   - TemporalNavigator class
   - Tests: `tests/unit/test_temporal.py`

2. **Temporal navigation agents**
   - Next moment generation
   - Prior moment generation
   - Batch stepping
   - Tests: `tests/integration/test_temporal_nav.py`

### Phase 4: Agent Rebuild (Week 4-5)

**Rebuild all 11 agents with:**
- Mirascope decorators
- Docstring examples
- Inline test references
- Type hints
- Pydantic models

**Order:**
1. Judge Agent (validation)
2. Timeline Agent (temporal extraction)
3. Scene Agent (environment)
4. Characters Agent (8 characters)
5. Moment Agent (plot)
6. Dialog Agent (7 lines)
7. Camera Agent (composition)
8. Graph Agent (relationships)
9. Image Prompt Agent (assembly)
10. Image Gen Agent (Nano Banana Pro)
11. Segmentation Agent (character masks)

**Each agent includes:**
- `app/agents/{name}.py` - implementation
- `tests/unit/test_{name}.py` - unit tests
- `tests/e2e/test_{name}_e2e.py` - integration tests

### Phase 5: CLI & API (Week 6)

1. **CLI Implementation**
   - `app/cli.py` with Click + Rich
   - Commands: generate, batch, models
   - Temporal navigation flags

2. **FastAPI Endpoints**
   - `/api/v1/timepoints/*` - CRUD
   - `/api/v1/temporal/*` - navigation
   - `/api/v1/batch/*` - batch processing
   - `/api/v1/models/*` - discovery

3. **HTMX Viewer**
   - `app/web/templates/viewer.html`
   - Temporal navigation UI
   - Real-time updates (SSE)

### Phase 6: Testing & Polish (Week 7)

1. **E2E test suite**
   - Full workflow tests
   - Temporal sequence tests
   - Batch processing tests
   - CLI tests

2. **Documentation**
   - README.md (v2)
   - QUICKSTART.md (v2)
   - API.md (OpenAPI docs)
   - TEMPORAL.md (time system guide)

3. **Performance optimization**
   - Parallel agent execution
   - Database query optimization
   - Caching layer

### Phase 7: Launch (Week 8)

1. **Final testing**
   - Full test suite passes
   - Coverage > 80%
   - Logfire monitoring

2. **Deployment**
   - Docker setup
   - Railway/Render config
   - PostgreSQL production database

3. **Release**
   - Git tag v2.0.0
   - GitHub release notes
   - Update documentation

---

## 9. Success Criteria

### Functional Requirements

✅ **One-command setup**: `pip install -e . && tp "rome 50 BCE"` → full render
✅ **Provider flexibility**: Google (pro) OR OpenRouter (multi) OR both
✅ **Temporal navigation**: Next/prior moment with context preservation
✅ **Batch processing**: CSV input → N timepoints
✅ **Model discovery**: OpenRouter API → dynamic model list
✅ **Clean API**: OpenAPI spec, HTMX viewer, SSE updates

### Technical Requirements

✅ **Test coverage**: >80% with fast/integration/e2e splits
✅ **Type safety**: Full mypy compliance
✅ **Observability**: Logfire integration for monitoring
✅ **Database**: SQLite (dev) + PostgreSQL (prod)
✅ **Performance**: <60s for full timepoint generation

### Developer Experience

✅ **Batteries included**: Zero config with API keys only
✅ **Clear architecture**: No abstraction hell, readable code
✅ **Good docs**: Docstrings with examples, README, guides
✅ **Easy testing**: `pytest -m fast` for instant feedback

---

## 10. Risk Mitigation

### Risk: Google API Limitations

**Mitigation:** OpenRouter fallback + model selection flexibility

### Risk: Migration Complexity

**Mitigation:** Phased approach with v1 archive, v2 clean slate

### Risk: Breaking Changes

**Mitigation:** API versioning (/api/v1/), clear deprecation notices

### Risk: Test Maintenance

**Mitigation:** Tight sync with docstrings, automated stub generation

---

## 11. Open Questions

1. **Synthetic Time Precision**: How to handle BCE dates? Lunar calendars?
2. **Temporal Context Size**: Full prior timepoint (10KB) or summary (1KB)?
3. **Batch Concurrency**: Default limit for parallel generation?
4. **Model Selection UI**: CLI flags sufficient or need config file?
5. **Archive Strategy**: Keep v1 branch live or delete after 3 months?

---

## 12. Next Steps

1. **Review this plan** with stakeholders
2. **Approve GitHub cleanup strategy** (destructive operation)
3. **Set up v2 branch** and clean slate
4. **Begin Phase 1** (GitHub cleanup)
5. **Daily standups** during rebuild (track progress)

---

**Document Status**: DRAFT
**Last Updated**: 2025-11-26
**Author**: Claude Code
**Approval Required**: Yes (destructive GitHub operations)
