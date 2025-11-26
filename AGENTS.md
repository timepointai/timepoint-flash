# AGENTS.md - AI Agent Guide for Timepoint Flash

**Target Audience**: AI Agents, LLMs, and autonomous systems working with this codebase.

This document provides a comprehensive technical overview of the Timepoint Flash API architecture, designed specifically for AI agents to understand and work with the codebase effectively.

---

## Quick Reference

**Repository**: https://github.com/realityinspector/timepoint-flash
**Language**: Python 3.11+
**Framework**: FastAPI + HTMX (web UI)
**Architecture**: LangGraph multi-agent orchestration
**Database**: SQLite (default) or PostgreSQL + SQLAlchemy ORM
**Primary Models**: Google Gemini 1.5 Pro, Gemini 2.5 Flash Image
**CLI Tool**: `tp` command (Click-based)
**Deployment**: Replit (configured), Docker, Railway-ready

**New Features (v1.0)**:
- ✨ CLI tool with `tp demo` for quick starts
- 🖼️ HTMX-powered web gallery (zero build step)
- 🗄️ SQLite auto-deploy (no database setup)
- 🧪 Smart database testing (SQLite ↔ PostgreSQL)

---

## CLI Tool (`app/cli.py`)

**Entry Point**: `tp` command (via pyproject.toml)

### Commands

```bash
tp generate "query"        # Generate single timepoint
tp list                     # List all timepoints
tp serve --port 5000       # Start server + gallery
tp demo                     # Generate 3 demo scenes + open browser
```

### Implementation Details

- **Framework**: Click (CLI framework)
- **Output**: Rich (terminal formatting with colors, tables, panels)
- **HTTP Client**: HTTPX (calls local API)
- **Auto-start**: Can start server automatically if not running
- **Browser Integration**: Opens gallery in default browser

### Demo Mode Flow

1. Check if demo timepoints exist (3 predefined queries)
2. Generate missing demos via API
3. Start server if not running
4. Open browser to gallery
5. Keep server running until Ctrl+C

---

## Web Gallery (`app/routers/gallery.py`)

**New in v1.0**: HTMX-powered web UI for viewing timepoints.

### Gallery Endpoints

#### `GET /`
**Purpose**: Gallery home (masonry grid)
**Template**: `gallery.html`
**Features**:
- Grid layout of all timepoints
- Infinite scroll (HTMX)
- Click to view details

#### `GET /view/{slug}`
**Purpose**: Single timepoint detailed view
**Template**: `viewer.html`
**Shows**:
- Full resolution image
- All character bios & appearances
- Complete dialog
- Scene metadata
- Generation time

#### `GET /generate`
**Purpose**: Interactive generation form
**Template**: `generate.html`
**Features**:
- Input form with validation
- Real-time SSE progress updates
- Live status display

#### `GET /demo`
**Purpose**: Demo landing page
**Template**: `demo.html`
**Content**: Explains demo mode, shows sample queries

### HTMX Partials

For dynamic loading:
- `GET /partials/timepoint-card/{slug}` - Single card HTML
- `GET /partials/feed-page?page=N` - Next page for infinite scroll

### Tech Stack

- **Templates**: Jinja2
- **Dynamic UX**: HTMX 1.9 (14KB)
- **CSS**: Water.css (classless) + custom styles
- **Real-time**: Server-Sent Events (SSE)

---

## System Overview

Timepoint Flash is a **photorealistic time travel API** that generates historically accurate scenes from any moment in history using orchestrated AI agents.

### Core Functionality

**Input**: User query (e.g., "medieval marketplace in London, winter 1250")
**Output**: Complete historical scene with:
- Year, season, location metadata
- 3-12 unique characters with bios, appearances, clothing
- Period-accurate dialog (10-20 lines)
- Scene setting, weather, environment
- Photorealistic image (Gemini 2.5 Flash Image)
- Segmented image with character labels
- NetworkX scene graph representation

**Processing Time**: ~45-60 seconds end-to-end

---

## Architecture: Multi-Agent Workflow

Timepoint Flash uses **LangGraph** to orchestrate 11 specialized AI agents in a directed acyclic graph (DAG). Each agent has a specific responsibility and operates on shared state.

### Workflow DAG

```
USER QUERY
    ↓
[1. JUDGE] ──✗─→ REJECT (END)
    ↓ ✓
[2. TIMELINE] ── Creates stub Timepoint record
    ↓
[3. SCENE BUILDER]
    ↓
[4. CHARACTERS] ── Parallel generation (3-12 characters)
    ↓
[5. MOMENT] ── Plot/dramatic interaction
    ↓
[6. DIALOG] ── Uses moment context
    ↓
[7. CAMERA] ── Cinematic directives
    ↓
[8. GRAPH BUILDER] ── NetworkX scene graph
    ↓
[9. IMAGE PROMPT COMPILER] ── Combines ALL context
    ↓
[10. IMAGE GENERATOR] ── Gemini 2.5 Flash Image
    ↓
[11. IMAGE SEGMENTATION] ── Character labeling
    ↓
COMPLETED → Database + Feed
```

### State Management

**Shared State** (`WorkflowState` in `app/agents/graph_orchestrator.py`):
- All agents read from and write to a shared typed dictionary
- State is immutable between nodes (functional programming pattern)
- Progressive updates: Database record updates in real-time as each agent completes

---

## Agent Specifications

### 1. Judge Agent (`app/agents/judge.py`)

**Purpose**: Validate and clean user input
**Model**: Gemini 1.5 Flash (fast validation)
**Input**: Raw user query
**Output**:
- `is_valid` (bool)
- `cleaned_query` (str) - Sanitized, improved query
- `rejection_reason` (str | None)

**Logic**:
- Rejects inappropriate content (violence, explicit material)
- Rejects impossible/nonsensical queries
- Rejects far-future dates (>2024)
- Cleans and normalizes valid queries

**Conditional**: If invalid, workflow ends immediately.

---

### 2. Timeline Agent (`app/agents/timeline.py`)

**Purpose**: Extract temporal and spatial metadata
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query
**Output**:
- `year` (int)
- `season` (str: "spring" | "summer" | "fall" | "winter")
- `location` (str: City, Country)
- `exact_date` (str, optional)
- `slug` (str: URL-friendly identifier)

**Side Effect**: **Creates stub Timepoint record in database** for progressive loading.

**URL Generation**: `/{year}/{season}/{slug}` (e.g., `/1250/winter/london-marketplace`)

---

### 3. Scene Builder Agent (`app/agents/scene_builder.py`)

**Purpose**: Build scene setting, environment, and props
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query + timeline data
**Output**:
- `setting`:
  - `environment` (str: "outdoor" | "indoor" | "mixed")
  - `architecture` (str)
  - `lighting` (str)
  - `atmosphere` (str)
  - `sounds` (list[str])
  - `smells` (list[str])
- `weather`:
  - `condition` (str)
  - `temperature` (str)
  - `visibility` (str)
- `props`: List of physical objects in scene
  - `name`, `description`, `location`, `state`

**Updates Database**: Scene data written to Timepoint record.

---

### 4. Characters Agent (`app/agents/characters.py`)

**Purpose**: Generate 3-12 unique, period-appropriate characters
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query + timeline + scene data
**Output**: List of characters, each with:
- `name` (str)
- `age` (int)
- `gender` (str)
- `role` (str: occupation/social position)
- `appearance` (str: physical description)
- `clothing` (str: period-accurate attire)
- `social_class` (str)
- `personality` (str)
- `background` (str)
- `motivations` (str)

**Constraints**:
- Minimum 3, maximum 12 characters
- Names must be period/culturally appropriate
- Clothing must match year, location, and social class
- Diverse representation within historical accuracy

**Updates Database**: Character data written to Timepoint record.

---

### 5. Moment Agent (`app/agents/moment.py`)

**Purpose**: Create a specific dramatic moment/interaction for the scene
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query + timeline + scene + characters
**Output**:
- `plot_summary` (str: What's happening right now)
- `tension_level` (str: "low" | "medium" | "high")
- `emotional_tone` (str)
- `narrative_beats` (list[str]: Sequence of micro-actions)
- `character_interactions` (list[dict]: Who's interacting with whom)
  - `characters` (list[str])
  - `interaction_type` (str: "conversation" | "conflict" | "cooperation")
  - `description` (str)

**Critical**: This context is **passed to Dialog Agent** to ensure dialog matches the dramatic moment.

---

### 6. Dialog Agent (`app/agents/dialog.py`)

**Purpose**: Generate period-accurate character dialog
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query + timeline + characters + scene + **moment**
**Output**: List of dialog lines (10-20 typical), each with:
- `speaker` (str: character name)
- `text` (str: what they say)
- `emotion` (str: emotional state)
- `action` (str: physical action while speaking)

**Historical Accuracy Requirements**:
- Language appropriate for time period (e.g., no anachronisms)
- Formal/informal register matches social class and setting
- Cultural references must be period-appropriate
- Dialect/accent considerations for location

**Updates Database**: Dialog data written to Timepoint record.

---

### 7. Camera Agent (`app/agents/camera.py`)

**Purpose**: Define cinematic camera angles and lighting
**Model**: Gemini 1.5 Pro
**Input**: Cleaned query + moment + characters + setting + year + location
**Output**:
- `angle` (str: "eye-level" | "low-angle" | "high-angle" | "dutch-angle")
- `distance` (str: "extreme-close-up" | "close-up" | "medium-shot" | "full-shot" | "wide-shot" | "extreme-wide-shot")
- `lens` (str: "wide" | "standard" | "telephoto" | "fisheye")
- `focal_point` (str: What the camera focuses on)
- `depth_of_field` (str: "shallow" | "deep")
- `framing` (str: Rule of thirds, composition notes)
- `camera_movement` (str: "static" | "pan" | "tilt" | "tracking" | "handheld")
- `lighting` (dict):
  - `primary_source` (str)
  - `quality` (str: "soft" | "hard" | "dramatic")
  - `color_temperature` (str)
  - `shadows` (str: shadow characteristics)

**Purpose in Pipeline**: These directives are compiled into the final image prompt.

---

### 8. Graph Builder (`app/agents/graph_orchestrator.py:graph_builder_node`)

**Purpose**: Build NetworkX scene graph representation
**Model**: Not an LLM - pure Python logic
**Input**: Setting + weather + characters + props
**Output**: NetworkX graph with:
- **Nodes**: Characters, props, locations
- **Edges**: Spatial relationships, character interactions
- **Attributes**: Node/edge metadata

**Data Structure**:
```python
{
    "nodes": [
        {"id": "char_1", "type": "character", "name": "..."},
        {"id": "prop_1", "type": "prop", "name": "..."}
    ],
    "edges": [
        {"source": "char_1", "target": "prop_1", "relation": "holding"}
    ]
}
```

**Not Used for Image Generation**: Primarily for future analysis/visualization.

---

### 9. Image Prompt Compiler (`app/services/scene_graph.py:graph_to_image_prompt`)

**Purpose**: Compile comprehensive image prompt from ALL available context
**Model**: Not an LLM - templating logic
**Input**:
- Scene graph
- Cleaned query
- Year & location
- **Moment** (plot, tension, emotional tone)
- **Dialog** (what characters are saying)
- **Characters** (full bios, appearance, clothing)
- **Setting** (environment, lighting, atmosphere)
- **Weather** (conditions)
- **Camera** (all directives)

**Output**: Single coherent prompt string for image generation (typically 800-1500 characters)

**Prompt Structure**:
```
[Time Period and Location]
[Camera Directives: angle, lens, lighting]
[Scene Setting: environment, architecture, atmosphere]
[Weather Conditions]
[Characters: detailed descriptions with clothing and positions]
[Dramatic Moment: what's happening, interactions]
[Dialog Context: key spoken lines]
[Artistic Style: photorealistic, historical accuracy, cinematic]
```

**Critical Design**: Combines **all** agent outputs to ensure image matches the complete narrative.

---

### 10. Image Generator (`app/services/google_ai.py:generate_image`)

**Purpose**: Generate photorealistic historical image
**Model**: Google Gemini 2.5 Flash Image (via Google AI SDK)
**Input**: Compiled image prompt
**Output**: Base64-encoded image data (PNG)

**Configuration**:
- Model: `gemini-2.5-flash-image-preview` (primary)
- Fallback: OpenRouter endpoint with same model
- Timeout: 60 seconds
- Error handling: Continues workflow even if image fails

**Storage**: Image data stored directly in database (no external object storage in current version).

**Updates Database**: Image URL written to Timepoint record **immediately** upon generation.

---

### 11. Image Segmentation (`app/services/google_ai.py:segment_image`)

**Purpose**: Identify and label characters in generated image
**Model**: Google Gemini 1.5 Pro (vision model)
**Input**:
- Generated image (Base64)
- Character names list

**Output**:
- `segmentation_image` or `segmentation_data` (labeled regions)
- `color_map` (dict mapping character names to colors)

**Method**: Uses Gemini Vision API to:
1. Analyze image
2. Identify character locations
3. Return bounding boxes or masks
4. Generate color-coded overlay

**Updates Database**: Segmented image written to Timepoint record.

---

## Database Schema

### Core Tables

**Database Support**: SQLite (default) and PostgreSQL

**UUID Handling**: Custom `UUID` TypeDecorator in `app/models.py`
- SQLite: Stores as String(36)
- PostgreSQL: Uses native UUID type
- Automatic dialect detection

#### `emails`
```sql
- id: UUID (PK)
- email: VARCHAR(255) UNIQUE
- created_at: TIMESTAMP
```

#### `timepoints`
```sql
- id: UUID (PK)
- email_id: UUID (FK → emails.id)
- slug: VARCHAR(500) UNIQUE
- year: INTEGER
- season: VARCHAR(50)
- input_query: TEXT
- cleaned_query: TEXT
- image_url: TEXT (Base64 PNG data)
- segmented_image_url: TEXT
- character_data_json: JSON (list of character objects)
- dialog_json: JSON (list of dialog lines)
- scene_graph_json: JSON (NetworkX graph)
- metadata_json: JSON (setting, weather, camera, location, etc.)
- processing_time_ms: INTEGER
- created_at: TIMESTAMP
```

#### `rate_limits`
```sql
- id: UUID (PK)
- email_id: UUID (FK → emails.id)
- timepoints_created: INTEGER
- window_start: TIMESTAMP
```

#### `processing_sessions`
```sql
- id: UUID (PK)
- session_id: VARCHAR(100) UNIQUE
- email_id: UUID (FK → emails.id)
- timepoint_id: UUID (FK → timepoints.id, nullable)
- status: ENUM (PENDING, VALIDATING, GENERATING_SCENE, GENERATING_IMAGE, COMPLETED, FAILED)
- progress_data_json: JSON
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

### Progressive Loading Pattern

**Key Insight**: Timepoint record is created **early** (in Timeline Agent) with minimal data, then **progressively updated** as each agent completes.

**Benefits**:
- User can navigate to timepoint URL immediately
- Frontend polls for updates every 2 seconds
- Real-time progress display
- Database acts as source of truth

---

## API Endpoints

### Public Endpoints

#### `GET /health`
**Purpose**: Health check
**Auth**: None
**Response**:
```json
{
  "status": "healthy",
  "service": "timepoint-flash"
}
```

#### `GET /`
**Purpose**: API root info
**Auth**: None
**Response**:
```json
{
  "service": "TIMEPOINT AI API",
  "status": "running",
  "version": "1.0.0",
  "docs": "/api/docs"
}
```

---

### Timepoint Endpoints

#### `POST /api/timepoint/create`
**Purpose**: Start timepoint generation
**Auth**: None (rate-limited by email)
**Request Body**:
```json
{
  "query": "medieval marketplace in London, winter 1250",
  "email": "user@example.com"
}
```

**Response** (immediate):
```json
{
  "session_id": "abc-123-def-456",
  "status": "pending",
  "message": "Timepoint generation started"
}
```

**Side Effects**:
1. Creates `ProcessingSession` record
2. Validates rate limit (1/hour default)
3. Spawns background task: `run_timepoint_workflow()`

**Rate Limiting**: Returns 429 if user exceeds `MAX_TIMEPOINTS_PER_HOUR` (default: 1).

---

#### `GET /api/timepoint/status/{session_id}`
**Purpose**: Server-Sent Events (SSE) stream for real-time progress
**Auth**: None
**Response**: SSE stream with events:

```
event: status
data: {"status": "validating", "progress": {"stage": "judge", "message": "Validating input..."}}

event: status
data: {"status": "generating_scene", "progress": {"stage": "timeline", "message": "Analyzing time period..."}}

event: status
data: {"status": "generating_scene", "progress": {"stage": "characters", "message": "Generating characters..."}}

event: status
data: {"status": "generating_image", "progress": {"stage": "image", "message": "Generating image..."}}

event: status
data: {"status": "completed", "timepoint_id": "xyz", "slug": "1250-winter-london-marketplace", "timepoint_url": "/1250/winter/london-marketplace"}

event: close
data: ""
```

**Client Usage**: Frontend opens EventSource connection, listens for `status` events, navigates to `timepoint_url` on completion.

---

#### `GET /api/timepoint/details/{year}/{season}/{slug}`
**Purpose**: Get complete timepoint data
**Auth**: None
**Response**:
```json
{
  "id": "uuid",
  "slug": "1250-winter-london-marketplace",
  "year": 1250,
  "season": "winter",
  "location": "London, England",
  "cleaned_query": "Medieval marketplace in London, winter 1250",
  "image_url": "data:image/png;base64,...",
  "segmented_image_url": "data:image/png;base64,...",
  "character_data": [
    {
      "name": "Thomas the Merchant",
      "role": "Cloth seller",
      "age": 45,
      "appearance": "Weathered face, gray beard",
      "clothing": "Wool tunic, leather apron",
      "social_class": "Merchant class",
      "personality": "Shrewd but fair",
      "background": "Third-generation cloth trader",
      "motivations": "Expand trade routes"
    }
  ],
  "dialog": [
    {
      "speaker": "Thomas",
      "text": "Fine wool from Flanders! Warmest in all of England!",
      "emotion": "Enthusiastic",
      "action": "Gesturing to fabric bolts"
    }
  ],
  "metadata": {
    "setting": {...},
    "weather": {...},
    "camera": {...},
    "moment": {...}
  },
  "scene_graph": {...},
  "processing_time_ms": 45000,
  "created_at": "2025-11-25T12:00:00Z"
}
```

---

#### `GET /api/feed?page=1&limit=50&show_future=false`
**Purpose**: List all timepoints (gallery/feed)
**Auth**: None
**Query Parameters**:
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50, max: 100)
- `show_future`: Include future dates (default: false)

**Response**:
```json
{
  "timepoints": [
    {
      "id": "uuid",
      "slug": "1250-winter-london-marketplace",
      "year": 1250,
      "season": "winter",
      "location": "London, England",
      "image_url": "data:image/png;base64,...",
      "created_at": "2025-11-25T12:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pages": 3
}
```

---

### Email Endpoints

#### `POST /api/email/verify`
**Purpose**: Verify email format
**Auth**: None
**Request Body**:
```json
{
  "email": "user@example.com"
}
```

**Response**:
```json
{
  "valid": true,
  "email": "user@example.com"
}
```

---

## Configuration

### Environment Variables

**Required** (choose one):
- `OPENROUTER_API_KEY`: OpenRouter key (includes Google models) **OR**
- `GOOGLE_API_KEY`: Direct Google AI API key

**Optional**:
- `DATABASE_URL`: Database connection (default: `sqlite:///./timepoint_local.db`)

**Optional**:
- `OPENROUTER_API_KEY`: Fallback LLM provider
- `LOGFIRE_TOKEN`: Observability/tracing
- `DEBUG`: Debug mode (default: false)
- `MAX_TIMEPOINTS_PER_HOUR`: Rate limit (default: 1)
- `SECRET_KEY`: JWT secret (if implementing auth)
- `ALLOWED_ORIGINS`: CORS origins (list)

### Model Configuration

Defined in `app/config.py`:
```python
JUDGE_MODEL = "gemini-1.5-flash"
VALIDATOR_MODEL = "gemini-1.5-pro"
IMAGE_MODEL = "google/gemini-2.5-flash-image-preview"
```

**Model Fallback**: If Google AI fails, system attempts OpenRouter endpoint with same model.

---

## Error Handling

### Workflow-Level Errors

**Strategy**: Each agent has try-catch blocks. If agent fails:
1. Error logged to `WorkflowState.errors[]`
2. Workflow continues with degraded functionality
3. Example: If image generation fails, workflow completes without image

**Critical Failures**: Only Judge Agent failure stops workflow (invalid query).

### Database Errors

**Transaction Safety**:
- All database writes use context managers (`get_db_context()`)
- Automatic rollback on exception
- Session expiration after updates to prevent stale reads

**Progressive Update Pattern**:
```python
async def update_timepoint_progressive(timepoint_id: str, **updates):
    """Progressively update timepoint as data becomes available."""
    with get_db_context() as db:
        db.expire_all()  # Prevent stale cache
        timepoint = db.query(Timepoint).filter(...).first()
        for key, value in updates.items():
            setattr(timepoint, key, value)
        db.commit()
        db.expire_all()  # Ensure next read is fresh
        await asyncio.sleep(0.05)  # Allow transaction visibility
```

---

## Testing

### Test Infrastructure

**Framework**: pytest with async support
**Configuration**: `pyproject.toml`

### Test Markers

```python
@pytest.mark.fast       # Unit tests, no external API calls (~5 seconds)
@pytest.mark.e2e        # End-to-end tests with real API (~5-10 minutes)
@pytest.mark.slow       # Long-running operations
@pytest.mark.postgres   # Tests requiring PostgreSQL (auto-skip if unavailable)
@pytest.mark.sqlite     # SQLite-specific behavior tests
```

### Smart Database Testing

**New in v1.0**: Tests automatically adapt to available database.

**Logic** (`tests/conftest.py`):
1. Read `DATABASE_URL` from environment
2. If SQLite URL → use it
3. If PostgreSQL URL → test connection:
   - If available → use PostgreSQL
   - If unavailable → fallback to in-memory SQLite (with warning)
4. If no DATABASE_URL → use in-memory SQLite

**Benefits**:
- ✅ Zero configuration for local testing
- ✅ PostgreSQL integration testing when available
- ✅ Graceful fallback (never fails due to DB)
- ✅ CI/CD friendly

**Usage**:
```bash
# Local (SQLite)
DATABASE_URL=sqlite:///./test.db pytest

# CI (in-memory)
pytest  # No DATABASE_URL set

# Integration (PostgreSQL)
DATABASE_URL=postgresql://localhost/test pytest
```

### Test Execution

```bash
# Fast tests (no API key required)
pytest -m fast

# E2E tests (requires OPENROUTER_API_KEY)
pytest -m e2e

# All tests
pytest
```

### LLM-Based Judge

**Location**: `tests/utils/llm_judge.py`
**Purpose**: Evaluate generated timepoint quality using Gemini 1.5 Pro

**Evaluation Criteria** (0-100 each):
- Historical Accuracy (30% weight)
- Character Quality (25% weight)
- Dialog Quality (25% weight)
- Scene Coherence (20% weight)

**Output Example**:
```python
JudgementResult(
    overall_score=76.5,
    historical_accuracy=82.0,
    character_quality=78.0,
    dialog_quality=72.0,
    scene_coherence=75.0,
    feedback="Strong historical accuracy with well-developed characters...",
    passed=True
)
```

**Usage in Tests**:
```python
judgement = await judge_timepoint(
    api_key=openrouter_api_key,
    query="medieval marketplace 1250",
    timepoint_data=timepoint_response,
    passing_threshold=70.0
)
assert judgement.passed
```

---

## Performance Characteristics

### Timing Breakdown (Typical)

| Stage | Duration | Notes |
|-------|----------|-------|
| Judge | 1-2s | Fast validation |
| Timeline | 2-3s | Extract metadata |
| Scene | 3-5s | Build setting |
| Characters | 5-8s | Generate 3-12 characters |
| Moment | 2-4s | Create dramatic moment |
| Dialog | 4-6s | Generate 10-20 lines |
| Camera | 2-3s | Define directives |
| Graph | <1s | Pure Python |
| Image Prompt | <1s | Template compilation |
| Image Generation | 15-25s | Gemini 2.5 Flash Image (longest stage) |
| Segmentation | 5-10s | Vision analysis |
| **Total** | **40-60s** | End-to-end |

### Resource Usage

**Memory**: ~200-500MB per request (mostly LLM context)
**Database**: ~50-200KB per timepoint (images are Base64 in DB)
**API Calls**: 10-15 LLM calls per timepoint

### Optimization Opportunities

1. **Parallel Agent Execution**: Currently sequential except Characters (already parallel)
   - Could parallelize: Scene + Timeline, Dialog + Camera
   - Tradeoff: More complex state management

2. **Image Storage**: Move images to object storage (S3, R2)
   - Current: Base64 in PostgreSQL
   - Benefit: Smaller DB, faster queries

3. **Caching**: Cache Judge results for identical queries
   - Benefit: Skip regeneration for duplicates

---

## Common Development Tasks

### Adding a New Agent

1. Create agent file in `app/agents/{agent_name}.py`
2. Define Pydantic models for input/output
3. Implement async function with Google AI client
4. Add agent node to `graph_orchestrator.py`
5. Update `WorkflowState` TypedDict with new fields
6. Add edge connections in `create_workflow()`
7. Update progressive database writes if needed

**Example**: Adding a "Music Agent" for period-appropriate soundtrack suggestions:

```python
# app/agents/music.py
from pydantic import BaseModel
import google.generativeai as genai

class MusicSuggestion(BaseModel):
    instruments: list[str]
    musical_style: str
    tempo: str
    mood: str

async def suggest_music(year: int, location: str, moment: dict) -> MusicSuggestion:
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = f"Suggest period-appropriate music for {year} in {location}..."
    response = await model.generate_content_async(prompt)
    return MusicSuggestion.parse_raw(response.text)
```

```python
# In graph_orchestrator.py
class WorkflowState(TypedDict):
    # ... existing fields
    music_suggestion: dict

async def music_node(state: WorkflowState) -> WorkflowState:
    music = await suggest_music(state["year"], state["location"]["name"], state["moment"])
    return {
        **state,
        "music_suggestion": music.dict(),
        "processing_steps": ["music_completed"]
    }

def create_workflow() -> StateGraph:
    workflow = StateGraph(WorkflowState)
    # ... existing nodes
    workflow.add_node("music", music_node)
    workflow.add_edge("moment", "music")  # After moment
    workflow.add_edge("music", "dialog")   # Before dialog
    return workflow.compile()
```

---

### Adding a New API Endpoint

1. Create/modify router file in `app/routers/`
2. Define Pydantic request/response models in `app/schemas.py`
3. Implement endpoint function with database access
4. Register router in `app/main.py`
5. Update API documentation

**Example**: Adding a "Search by Year" endpoint:

```python
# app/routers/timepoint.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Timepoint

router = APIRouter()

@router.get("/search/year/{year}")
async def search_by_year(
    year: int,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get all timepoints for a specific year."""
    timepoints = (
        db.query(Timepoint)
        .filter(Timepoint.year == year)
        .order_by(Timepoint.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "year": year,
        "count": len(timepoints),
        "timepoints": [tp.to_dict() for tp in timepoints]
    }
```

---

### Database Migrations

**Tool**: Alembic
**Workflow**:

1. Modify models in `app/models.py`
2. Generate migration:
   ```bash
   alembic revision --autogenerate -m "description"
   ```
3. Review migration in `alembic/versions/{hash}_{description}.py`
4. Apply migration:
   ```bash
   alembic upgrade head
   ```
5. Rollback if needed:
   ```bash
   alembic downgrade -1
   ```

**Best Practices**:
- Always review auto-generated migrations
- Test migrations on staging database first
- Never edit applied migrations; create new ones

---

## Deployment

### Replit (Configured)

**Files**:
- `.replit`: Run configuration
- `init.sh`: Setup script

**Steps**:
1. Import repo to Replit
2. Set secrets in Replit Secrets panel:
   - `DATABASE_URL`
   - `GOOGLE_API_KEY`
3. Run project (auto-starts from `.replit`)

**URL**: Auto-generated by Replit (e.g., `https://{project-name}.{username}.repl.co`)

---

### Docker

**Build**:
```bash
docker build -t timepoint-flash .
```

**Run**:
```bash
docker run -p 5000:5000 --env-file .env timepoint-flash
```

**Dockerfile** includes:
- Python 3.11 slim image
- PostgreSQL client libraries
- Alembic migrations on startup
- Uvicorn ASGI server

---

### Railway / Render / Fly.io

**Steps**:
1. Push repo to GitHub
2. Connect to platform
3. Set environment variables
4. Auto-deploy on push

**Health Check**: `GET /health` for monitoring

---

## Observability

### Logging

**Framework**: Python `logging` module
**Format**: Structured logs with agent names

**Example Log Output**:
```
2025-11-25 12:00:00 - INFO - [JUDGE] Starting validation for query: medieval marketplace...
2025-11-25 12:00:02 - INFO - [JUDGE] Validation complete - Valid: True
2025-11-25 12:00:02 - INFO - [TIMELINE] Generating timeline for: Medieval marketplace...
2025-11-25 12:00:05 - INFO - [TIMELINE] Complete - Year: 1250, Season: winter, Location: London
```

**Stages Logged**:
- Each agent start/completion
- Database updates
- Image generation progress
- Errors with stack traces

---

### Logfire Integration (Optional)

**Tool**: Pydantic Logfire
**Setup**: Set `LOGFIRE_TOKEN` in `.env`
**Instrumentation**: Automatic FastAPI instrumentation

**Traces**:
- API request timing
- Agent execution duration
- Database query performance
- External API calls (Google, OpenRouter)

**Dashboard**: https://logfire.pydantic.dev/

---

## Security Considerations

### Rate Limiting

**Mechanism**: Email-based, enforced at database level
**Default**: 1 timepoint per hour
**Override**: Set `MAX_TIMEPOINTS_PER_HOUR` in environment

**Bypass**: Currently no authentication, so users can use multiple emails.
**Future Enhancement**: Require email verification or IP-based rate limiting.

---

### Input Validation

**Judge Agent** rejects:
- Explicit violence or sexual content
- Nonsensical queries
- Far-future dates (>2024)

**Database Constraints**:
- Email format validation
- Unique slugs (with collision handling)
- Required fields enforced by ORM

---

### API Security

**Current**: No authentication (public API)
**CORS**: Configurable via `ALLOWED_ORIGINS`
**Headers**: Standard FastAPI security headers

**Future Enhancements**:
- JWT authentication
- API key system
- Request signing

---

## Troubleshooting Guide

### Common Issues

#### 1. "OPENROUTER_API_KEY not found"
**Solution**: Export key or add to `.env`:
```bash
export OPENROUTER_API_KEY="your-key"
```

#### 2. Database connection errors
**Check**:
- `DATABASE_URL` is correct
- PostgreSQL is running
- Migrations applied: `alembic upgrade head`

#### 3. Image generation timeout
**Causes**:
- Gemini API overloaded
- Network issues
- Prompt too complex

**Solutions**:
- Retry with same query
- Simplify query
- Check Google AI API status

#### 4. SSE stream not updating
**Debug**:
- Check `ProcessingSession` status in database
- Verify background task is running (check logs)
- Test with `/api/timepoint/details/{slug}` directly

---

## FAQ for AI Agents

**Q: Can I run agents in parallel?**
A: Characters agent already runs in parallel (generates 3-12 characters concurrently). Other agents are sequential due to data dependencies. Future optimization possible for independent agents.

**Q: How do I change the image model?**
A: Modify `IMAGE_MODEL` in `app/config.py`. Must be compatible with Google AI SDK or OpenRouter.

**Q: Can I add non-LLM agents?**
A: Yes. Graph Builder is pure Python. Any agent can use deterministic logic instead of LLMs.

**Q: How do I access intermediate workflow state?**
A: Check `ProcessingSession.progress_data_json` in database. Updated in real-time by each agent.

**Q: What happens if an agent fails?**
A: Error logged, workflow continues. Only Judge failure stops execution. Final timepoint may have partial data.

**Q: Can I modify prompts without changing code?**
A: Currently prompts are hardcoded in agent files. Future: Move to external prompt templates (JSON/YAML).

**Q: How do I add a new character attribute?**
A: 1) Update `Character` Pydantic model in `app/agents/characters.py`, 2) Update character generation prompt, 3) Database schema auto-updates (JSON field).

**Q: Is there a webhook system?**
A: No. Currently poll-based (SSE). Future enhancement: Webhooks for completion notifications.

---

## References

- **LangGraph Documentation**: https://langchain-ai.github.io/langgraph/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Google AI SDK**: https://ai.google.dev/docs
- **SQLAlchemy Documentation**: https://docs.sqlalchemy.org/
- **Pydantic Documentation**: https://docs.pydantic.dev/

---

## Version Information

**Current Version**: 1.0.0
**Last Updated**: 2025-11-25
**Python Version**: 3.11+
**API Version**: v1 (no versioning in endpoints yet)

---

**End of AGENTS.md**

This document is maintained for AI agents and autonomous systems. For human-readable documentation, see [README.md](README.md).
